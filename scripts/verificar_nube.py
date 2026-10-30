"""Comprueba HTTPS, conexión y sesiones reales; no crea ventas ni modifica catálogos."""
import argparse
from datetime import datetime, timezone
from http.cookiejar import CookieJar
import json
from pathlib import Path
import ssl
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPCookieProcessor, HTTPSHandler, Request, build_opener

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


class SinRedireccion(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('El servidor intentó redirigir la comprobación. Revisa la URL principal antes de enviar credenciales.')


def verificar(origen, auditoria=False, seguridad=False):
    u=urlsplit(origen)
    if (u.scheme!='https' or not u.hostname or u.username or u.password or u.path not in ('','/')
            or u.query or u.fragment or u.port or not u.hostname.endswith(('.vercel.app','.onrender.com'))):
        raise ValueError('Utiliza la URL HTTPS principal del despliegue, sin rutas ni credenciales.')
    origen='https://'+u.hostname
    claves=dotenv_values(ROOT/'.local/NUBE_PRIVADO.env')
    resultados=[]

    def comprobar(condicion, nombre):
        if not condicion:
            raise RuntimeError(nombre)
        resultados.append(nombre)

    for correo,variable,rol,ruta,permitida in (
        ('admin@puntocom.demo','DEMO_ADMIN_PASSWORD','Administrador','/dashboard',True),
        ('cajero@puntocom.demo','DEMO_CAJERO_PASSWORD','Cajero','/inventario',False),
        ('bodega@puntocom.demo','DEMO_BODEGA_PASSWORD','Bodeguero','/ventas',False),
    ):
        jar=CookieJar()
        cliente=build_opener(HTTPSHandler(context=ssl.create_default_context()),HTTPCookieProcessor(jar),SinRedireccion())

        def pedir(path,metodo='GET',body=None,headers=None):
            h=dict(headers or {})
            if metodo != 'GET':
                h['Origin']=origen
            if body is not None:
                h['Content-Type']='application/json'
            req=Request(origen+'/api'+path,data=json.dumps(body).encode() if body is not None else None,headers=h,method=metodo)
            try:
                respuesta=cliente.open(req,timeout=90)
            except HTTPError as error:
                respuesta=error
            with respuesta:
                return respuesta.status,json.loads(respuesta.read()),respuesta.headers

        def csrf():
            return {'X-CSRF-TOKEN':next(c.value for c in jar if c.name=='csrf_refresh_token')}

        estado,datos,_=pedir('/health')
        comprobar(estado==200 and datos.get('base_datos')=='conectada','Base remota conectada: '+rol)
        comprobar(pedir('/auth/me')[0]==401,'Acceso anónimo rechazado: '+rol)
        estado,datos,cabeceras=pedir('/auth/login','POST',{'correo':correo,'password':claves[variable]})
        if datos.get('requiere_2fa'):
            raise RuntimeError('La cuenta '+rol+' ya tiene 2FA activo: completa su ingreso manualmente; esta prueba no solicita códigos personales.')
        comprobar(estado==200 and 'access_token' in datos,
                  'Ingreso correcto: '+rol+' (HTTP '+str(estado)+')')
        token=datos['access_token']
        cookie=next(c for c in jar if c.name=='refresh_token_cookie')
        comprobar(cookie.secure and cookie.has_nonstandard_attr('HttpOnly') and cookie.get_nonstandard_attr('SameSite')=='Strict','Cookie segura: '+rol)
        comprobar(cabeceras.get('Cache-Control')=='no-store','Sin caché de sesión: '+rol)
        h={'Authorization':'Bearer '+token}
        estado,datos,_=pedir('/auth/me',headers=h)
        comprobar(estado==200 and datos.get('rol')==rol,'Rol desde PostgreSQL: '+rol)
        usuario_id=datos.get('id')
        if seguridad:
            estado,config,_=pedir('/auth/mfa',headers=h)
            comprobar(estado==200 and isinstance(config.get('activo'),bool)
                      and isinstance(config.get('respaldos_restantes'),int),'Consulta privada de estado 2FA: '+rol)
        if auditoria:
            estado,bitacora,_=pedir('/auditoria?modulo=accesos&limite=5',headers=h)
            comprobar(estado==(200 if rol=='Administrador' else 403),'Permisos de bitácora: '+rol)
            if rol=='Administrador':
                comprobar(any(e['accion']=='INICIAR_SESION' and e['id_usuario']==usuario_id for e in bitacora['data']),
                          'Ingreso persistido en bitácora remota')
        comprobar(pedir(ruta,headers=h)[0]==(200 if permitida else 403),'Permisos correctos: '+rol)
        estado,datos,_=pedir('/auth/refresh','POST',headers=csrf())
        comprobar(estado==200 and datos.get('access_token'),'Renovación real: '+rol)
        h={'Authorization':'Bearer '+datos['access_token']}
        comprobar(pedir('/auth/me',headers=h)[0]==200,'Sesión renovada utilizable: '+rol)
        if auditoria and rol=='Administrador':
            estado,bitacora,_=pedir('/auditoria?modulo=accesos&accion=RENOVAR_SESION&usuario='+str(usuario_id),headers=h)
            comprobar(estado==200 and bitacora['total']>0,'Renovación persistida en bitácora remota')
        comprobar(pedir('/auth/logout','POST',headers=csrf())[0]==200,'Cierre de sesión: '+rol)
        comprobar(pedir('/auth/me',headers=h)[0]==401,'Token revocado tras salir: '+rol)
        print('HTTPS, PostgreSQL y sesión comprobados para',rol,flush=True)
    reporte=dict(fecha=datetime.now(timezone.utc).isoformat(),url=origen,comprobaciones=len(resultados),
                 resultado='correcto',casos=resultados,datos_negocio_modificados=False,auditoria_verificada=auditoria,
                 estado_2fa_consultado=seguridad,configuracion_2fa_modificada=False)
    (ROOT/'docs/resultado_nube.json').write_text(json.dumps(reporte,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Comprobaciones correctas:',len(resultados))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--auditoria',action='store_true',help='Comprueba el historial de accesos y sus permisos sin cambiar catálogos.')
    parser.add_argument('--seguridad',action='store_true',help='Consulta el estado privado de 2FA sin vincular ni activar cuentas.')
    try:
        args=parser.parse_args()
        verificar(args.url,args.auditoria,args.seguridad)
    except Exception as error:
        # No mostrar respuestas, cuerpos de peticiones, JWT ni conexiones privadas.
        detalle=str(error) if isinstance(error, RuntimeError) else type(error).__name__
        raise SystemExit('No se completó la comprobación pública: '+detalle) from None
