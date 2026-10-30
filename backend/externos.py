"""Tres proveedores públicos. No se transmiten datos del negocio ni credenciales."""
from datetime import date,datetime,timezone
import json,math,threading,time,re
from urllib.parse import urlencode
from urllib.request import Request,HTTPRedirectHandler,build_opener
from urllib.error import HTTPError
from flask import Blueprint,jsonify,request
from backend.auth import proteger
from configuracion import TZ

externos_bp=Blueprint('externos',__name__,url_prefix='/api/externos')
FUENTES={
 'cambio':('Frankfurter','https://frankfurter.dev/',3600,86400),
 'feriados':('Nager.Date','https://github.com/nager/Nager.Date',86400,604800),
 'dominio':('Google Public DNS','https://developers.google.com/speed/public-dns/docs/doh/json',3600,0),
}
_cache={};_lock=threading.Lock()

class SinRedireccion(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Redirección externa rechazada.')

def obtener_json(url):
    # URL construida exclusivamente por este módulo; ninguna dirección viene del cliente.
    with build_opener(SinRedireccion()).open(Request(url,headers={'Accept':'application/json','User-Agent':'PuntoCom-academico/1.0'}),timeout=5) as respuesta:
        if respuesta.status!=200:raise ValueError('Respuesta inesperada.')
        contenido=respuesta.read(524289)
        if len(contenido)>524288:raise ValueError('Respuesta demasiado grande.')
        return json.loads(contenido)

def numero(valor,minimo,maximo):
    if isinstance(valor,bool) or not isinstance(valor,(int,float)) or not math.isfinite(valor) or not minimo<=valor<=maximo:
        raise ValueError('Dato numérico inválido del proveedor.')
    return valor

def validar_dominio(valor):
    if not isinstance(valor,str) or len(valor)>253:raise ValueError('Escribe solo un dominio público, por ejemplo ejemplo.com.')
    try:dominio=valor.strip().rstrip('.').encode('idna').decode('ascii').lower()
    except UnicodeError:raise ValueError('El dominio no es válido.') from None
    partes=dominio.split('.')
    if len(partes)<2 or not re.fullmatch(r'(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})',partes[-1]) or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',p) for p in partes):
        raise ValueError('Escribe solo el dominio, sin correo completo, enlaces, rutas ni direcciones IP.')
    return dominio

def consultar_proveedor(tipo,anio):
    if tipo=='cambio':
        d=obtener_json('https://api.frankfurter.dev/v2/rate/USD/GTQ')
        if d['base']!='USD' or d['quote']!='GTQ':raise ValueError('Monedas incorrectas.')
        fecha=date.fromisoformat(d['date'])
        if not 0<=(datetime.now(TZ).date()-fecha).days<=10:raise ValueError('Cotización fuera del período esperado.')
        return dict(fecha=fecha.isoformat(),base='USD',moneda='GTQ',tasa=numero(d['rate'],.01,1000))
    if tipo=='feriados':
        d=obtener_json(f'https://nagerholidays.com/api/v3/publicholidays/{anio}/GT')
        if not isinstance(d,list) or len(d)>100:raise ValueError('Calendario inválido.')
        resultado=[]
        for f in d:
            dia=date.fromisoformat(f['date'])
            if dia.year!=anio or f['countryCode']!='GT' or not isinstance(f['global'],bool):raise ValueError('País o año incorrecto.')
            nombre=f.get('localName') or f['name']
            if not isinstance(nombre,str) or not 0<len(nombre)<=200:raise ValueError('Nombre inválido.')
            resultado.append(dict(fecha=dia.isoformat(),nombre=nombre,nacional=f['global']))
        return dict(anio=anio,feriados=sorted(resultado,key=lambda f:f['fecha']))
    dominio=validar_dominio(anio)
    d=obtener_json('https://dns.google/resolve?'+urlencode({'name':dominio,'type':'MX','edns_client_subnet':'0.0.0.0/0'}))
    if type(d.get('Status')) is not int or d['Status'] not in (0,3):raise ValueError('Consulta DNS no completada.')
    registros=[]
    for registro in d.get('Answer',[]):
        if registro.get('type')!=15:continue
        dato=registro.get('data','')
        if not isinstance(dato,str) or len(dato)>260:raise ValueError('Registro MX inválido.')
        partes=dato.split()
        if len(partes)!=2 or not partes[0].isdigit() or not 0<=int(partes[0])<=65535:raise ValueError('Registro MX inválido.')
        servidor=partes[1]
        if servidor!='.':validar_dominio(servidor)
        registros.append(dict(prioridad=int(partes[0]),servidor=servidor))
    if d['Status']==3:estado='no_existe'
    elif any(r['servidor']=='.' and r['prioridad']==0 for r in registros):estado='no_recibe'
    elif registros:estado='con_mx'
    else:estado='sin_mx'
    return dict(dominio=dominio,resultado=estado,registros=registros)

def consultar(tipo,anio=None):
    if tipo not in FUENTES:raise ValueError('Servicio desconocido.')
    fuente,enlace,ttl,limite=FUENTES[tipo]
    if tipo=='dominio':anio=validar_dominio(anio)
    clave=(tipo,anio if tipo in ('feriados','dominio') else None)
    ahora=time.monotonic()
    with _lock:guardado=_cache.get(clave)
    if guardado and ahora-guardado[0]<ttl:
        return dict(ok=True,estado='cache',datos=guardado[1],consultado=guardado[2],fuente=fuente,enlace=enlace)
    try:
        datos=consultar_proveedor(tipo,anio)
        marca=datetime.now(timezone.utc).isoformat()
        with _lock:
            # Caché acotada incluso si se consultan dominios diferentes.
            _cache[clave]=(time.monotonic(),datos,marca)
            if len(_cache)>8:_cache.pop(next(iter(_cache)))
        return dict(ok=True,estado='actualizado',datos=datos,consultado=marca,fuente=fuente,enlace=enlace)
    except Exception as error:
        # No devolver mensajes externos ni registrar URLs, cookies o cuerpos de respuestas.
        if guardado and time.monotonic()-guardado[0]<limite:
            return dict(ok=True,estado='desactualizado',datos=guardado[1],consultado=guardado[2],fuente=fuente,enlace=enlace,
                        aviso='El proveedor no respondió. Se muestra la última consulta guardada; comprueba su fecha.')
        return dict(ok=False,estado='no_disponible',datos=None,consultado=None,fuente=fuente,enlace=enlace,
                    codigo_error=('http_'+str(error.code)) if isinstance(error,HTTPError) else type(error).__name__,
                    aviso='Servicio temporalmente no disponible. Puedes seguir trabajando en el sistema.')

@externos_bp.get('/<tipo>')
@proteger('herramientas.ver')
def servicio(tipo):
    if tipo not in FUENTES:
        from flask import abort
        abort(404)
    anio=datetime.now(TZ).year
    if tipo=='feriados':
        try:anio=int(request.args.get('anio',anio))
        except (ValueError,TypeError):raise ValueError('Selecciona un año válido.')
        if abs(anio-datetime.now(TZ).year)>1:raise ValueError('Consulta el año actual, anterior o siguiente.')
    if tipo=='dominio':anio=validar_dominio(request.args.get('dominio',''))
    return jsonify(consultar(tipo,anio))
