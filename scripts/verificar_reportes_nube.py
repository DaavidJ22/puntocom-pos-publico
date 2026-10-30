"""Descargas y permisos de reportes en el destino HTTPS de demostración autorizado."""
from http.cookiejar import CookieJar
from urllib.request import build_opener,HTTPCookieProcessor,Request
from urllib.error import HTTPError
from pathlib import Path
from io import BytesIO
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from verificar_nube import SinRedireccion
from dotenv import dotenv_values
from openpyxl import load_workbook

def main():
    origen='https://puntocom-demo-analisis2.vercel.app'
    claves=dotenv_values(ROOT/'.local/NUBE_PRIVADO.env');casos=[]
    for cuenta,key,permitidos in [('admin','ADMIN',{'ventas','productos','inventario','compras','caja'}),
                                ('cajero','CAJERO',{'ventas','productos','caja'}),('bodega','BODEGA',{'inventario'})]:
        jar=CookieJar();cliente=build_opener(HTTPCookieProcessor(jar),SinRedireccion())
        def pedir(ruta,body=None,headers=None):
            h=headers or {}
            if body is not None:h={**h,'Content-Type':'application/json','Origin':origen}
            req=Request(origen+'/api/'+ruta,data=json.dumps(body).encode() if body is not None else None,headers=h)
            try:r=cliente.open(req,timeout=90)
            except HTTPError as error:r=error
            with r:return r.status,r.read()
        estado,cuerpo=pedir('auth/login',{'correo':cuenta+'@puntocom.demo','password':claves['DEMO_'+key+'_PASSWORD']})
        datos=json.loads(cuerpo)
        if estado!=200 or 'access_token' not in datos:raise RuntimeError('Ingreso no disponible o requiere segundo factor: '+cuenta)
        h={'Authorization':'Bearer '+datos['access_token']}
        for tipo in ('ventas','productos','inventario','compras','caja'):
            for formato in ('','/pdf','/excel'):
                estado,cuerpo=pedir('informes/'+tipo+formato,headers=h)
                if estado!=(200 if tipo in permitidos else 403):raise RuntimeError(f'{cuenta}: {tipo}{formato} HTTP {estado}')
                if estado==200:
                    if formato=='/pdf' and not cuerpo.startswith(b'%PDF'):raise RuntimeError('PDF inválido')
                    if formato=='/excel':
                        libro=load_workbook(BytesIO(cuerpo));libro.close()
                    if not formato:json.loads(cuerpo)
                casos.append(cuenta+': '+tipo+formato)
        csrf=next(c.value for c in jar if c.name=='csrf_refresh_token')
        if pedir('auth/logout',{},headers={'X-CSRF-TOKEN':csrf})[0]!=200:raise RuntimeError('No se pudo cerrar sesión de prueba.')
        print('Reportes y permisos comprobados:',cuenta,flush=True)
    (ROOT/'docs/resultado_reportes_nube.json').write_text(json.dumps(dict(url=origen,casos=casos,comprobaciones=len(casos),resultado='correcto',datos_negocio_modificados=False),indent=2)+'\n',encoding='utf-8')
    print('Comprobaciones:',len(casos))

if __name__=='__main__':
    try:main()
    except Exception as error:raise SystemExit(str(error) if isinstance(error,RuntimeError) else type(error).__name__) from None
