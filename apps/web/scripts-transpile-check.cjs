const fs=require('fs'); const path=require('path'); const ts=require('typescript');
const root=path.resolve(__dirname);
const files=[];
function walk(dir){for(const e of fs.readdirSync(dir,{withFileTypes:true})){const p=path.join(dir,e.name);if(e.isDirectory()){if(!['node_modules','.next'].includes(e.name))walk(p)}else if((p.endsWith('.ts')||p.endsWith('.tsx'))&&!p.endsWith('.d.ts'))files.push(p)}}
walk(path.join(root,'app')); walk(path.join(root,'components')); walk(path.join(root,'lib')); if(fs.existsSync(path.join(root,'e2e')))walk(path.join(root,'e2e')); if(fs.existsSync(path.join(root,'playwright.config.ts')))files.push(path.join(root,'playwright.config.ts'));
let errors=[];
for(const f of files){const src=fs.readFileSync(f,'utf8');const out=ts.transpileModule(src,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext},fileName:f,reportDiagnostics:true});for(const d of out.diagnostics||[]){if(d.category===ts.DiagnosticCategory.Error)errors.push(`${path.relative(root,f)}: ${ts.flattenDiagnosticMessageText(d.messageText,' ')}`)}}
console.log(JSON.stringify({files:files.length,errors},null,2)); process.exit(errors.length?1:0);
