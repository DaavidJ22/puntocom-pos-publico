import React,{useEffect,useState} from 'react';
import {api,download} from './api';
import {Heading,Table,Notice,q} from './components';
const tipos=[['ventas','Ventas','reportes.ventas'],['productos','Productos más vendidos','reportes.ventas'],['inventario','Inventario actual','inventario.ver'],['compras','Compras','proveedores.gestionar'],['caja','Movimientos de caja','ventas.registrar']];
export default function Informes({can}){
 const disponibles=tipos.filter(t=>can(t[2]));
 const [tipo,setTipo]=useState(disponibles[0][0]),[filtro,setFiltro]=useState(''),[data,setData]=useState(null),[error,setError]=useState(''),[ocupado,setOcupado]=useState(false),[cargando,setCargando]=useState(true);
 useEffect(()=>{let activo=true;setData(null);setError('');setCargando(true);api('/informes/'+tipo+filtro).then(d=>{if(activo)setData(d)}).catch(e=>{if(activo)setError(e.message)}).finally(()=>{if(activo)setCargando(false)});return()=>{activo=false}},[tipo,filtro]);
 async function exportar(formato){setOcupado(true);setError('');try{await download('/informes/'+tipo+'/'+formato+filtro,'PuntoCom_'+tipo+(formato==='pdf'?'.pdf':'.xlsx'))}catch(e){setError(e.message)}finally{setOcupado(false)}}
 return <><Heading title="Reportes" description="Consulta los datos del negocio y descarga el mismo resultado en PDF o Excel.">
 <button className="btn tonal" disabled={!data||ocupado||cargando} onClick={()=>exportar('pdf')}>Descargar PDF</button><button className="btn" disabled={!data||ocupado||cargando} onClick={()=>exportar('excel')}>Descargar Excel</button></Heading>
 <Notice message={error}/><section className="surface"><label className="field"><span>Reporte</span><select className="browser-default" value={tipo} onChange={e=>{setTipo(e.target.value);setFiltro('')}}>{disponibles.map(([id,titulo])=><option key={id} value={id}>{titulo}</option>)}</select></label>
 {tipo!=='inventario'&&<form className="filter-bar" key={tipo} onSubmit={e=>{e.preventDefault();setFiltro('?'+new URLSearchParams(new FormData(e.currentTarget)))}}>
 <label className="field"><span>Desde</span><input type="date" name="desde" required defaultValue={data?.desde} key={'d'+data?.desde}/></label><label className="field"><span>Hasta</span><input type="date" name="hasta" required defaultValue={data?.hasta} key={'h'+data?.hasta}/></label><button className="btn tonal" disabled={cargando}>Aplicar filtro</button></form>}</section>
 {cargando&&<p role="status">Consultando reporte…</p>}{data&&<section className="surface section-space"><h2>{data.titulo}</h2><p>{data.nota}</p><p><strong>{data.cantidad}</strong> registros{tipo!=='inventario'&&<> · {tipo==='caja'?'Movimiento neto':'Total'}: <strong>{q(data.total)}</strong></>}</p>
 <Table data={data.data} columns={data.columnas.map(([k,t])=>[k,t,(v)=>/total|monto|precio/.test(k)?q(v):String(v??'—')])}/></section>}</>;
}
