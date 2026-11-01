const fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const root=__dirname, resolve=Module.createRequire(path.join(root,'package.json'));
const esbuild=resolve('esbuild'), mod=new Module('nanotox-views',module);
const output=esbuild.buildSync({entryPoints:[path.join(root,'views.tsx')],bundle:true,platform:'node',format:'cjs',write:false,nodePaths:(process.env.NODE_PATH||'').split(path.delimiter).filter(Boolean),define:{'process.env.NODE_ENV':'"production"'}});
mod._compile(output.outputFiles[0].text,path.join(root,'views.cjs'));
const t=mod.exports.templates;
const frame=fs.readFileSync(path.join(root,'studio.template.html'),'utf8').replace('<!--SHADCN_FILTERS-->',t.filters).replace('<!--SHADCN_DOWNLOAD-->',t.download).replace('/*SHADCN_TEMPLATES*/',()=>JSON.stringify(t).replace(/</g,'\\u003c'));
fs.writeFileSync(path.join(root,'../studio.html'),frame);
