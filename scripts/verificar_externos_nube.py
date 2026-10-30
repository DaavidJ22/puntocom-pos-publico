"""Comprobación de las tres APIs desde la nube sin enviar datos del negocio."""
from pathlib import Path
import sys,json
from datetime import datetime,timezone
from http.cookiejar import CookieJar
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from verificar_nube import SinRedireccion
from dotenv import dotenv_values

def main():
    origen='https://puntocom-demo-analisis2.vercel.app'
    claves=dotenv_values(ROOT/'.local/NUBE_PRIVADO.env');casos=[]
    for cuenta,key in [('admin','ADMIN'),('cajero','CAJERO'),('bodega','BODEGA')]:
        jar=CookieJar();cliente=build_opener(HTTPCookieProcessor(jar),SinRedireccion())
        def pedir(ruta,body=None,headers=None):
            h=dict(headers or {})
            if body is not None:h.update({'Origin':origen,'Content-Type':'application/json'})
            req=Request(origen+'/api/'+ruta,data=json.dumps(body).encode() if body is not None else None,headers=h)
            try:r=cliente.open(req,timeout=90)
            except HTTPError as error:r=error
            with r:return r.status,json.load(r)
        if cuenta=='admin':
            if pedir('externos/cambio')[0]!=401:raise RuntimeError('No se rechazó el acceso anónimo.')
            casos.append({'caso':'acceso anónimo','estado':'rechazado'})
        estado,d=pedir('auth/login',{'correo':cuenta+'@puntocom.demo','password':claves['DEMO_'+key+'_PASSWORD']})
        if estado!=200 or 'access_token' not in d:raise RuntimeError('Ingreso no disponible o requiere 2FA: '+cuenta)
        h={'Authorization':'Bearer '+d['access_token']}
        for tipo in ('cambio','feriados','dominio?dominio=gmail.com'):
            estado,d=pedir('externos/'+tipo,headers=h)
            if estado!=200 or not d.get('ok'):raise RuntimeError('Servicio no disponible desde la nube: '+tipo+' ('+str(d.get('codigo_error',estado))+')')
            casos.append({'perfil':cuenta,'servicio':tipo,'estado':d['estado'],'fuente':d['fuente'],'consultado':d['consultado']})
        if pedir('externos/feriados?anio=1900',headers=h)[0]!=400:raise RuntimeError('Año inválido aceptado.')
        casos.append({'perfil':cuenta,'caso':'año inválido','estado':'rechazado'})
        csrf=next(c.value for c in jar if c.name=='csrf_refresh_token')
        if pedir('auth/logout',{},headers={'X-CSRF-TOKEN':csrf})[0]!=200:raise RuntimeError('Cierre no completado.')
        print('Integraciones reales comprobadas:',cuenta,flush=True)
    reporte={'fecha':datetime.now(timezone.utc).isoformat(),'url':origen,'comprobaciones':len(casos),'casos':casos,'resultado':'correcto','datos_negocio_modificados':False}
    (ROOT/'docs/resultado_externos_nube.json').write_text(json.dumps(reporte,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Comprobaciones:',len(casos))

if __name__=='__main__':
    try:main()
    except Exception as error:raise SystemExit(str(error) if isinstance(error,RuntimeError) else type(error).__name__) from None
