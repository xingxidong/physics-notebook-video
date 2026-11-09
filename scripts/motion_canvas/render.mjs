// Real Motion Canvas Renderer + headless Chrome; streamed PNG frames are encoded locally.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {spawn} from 'node:child_process';
const args=Object.fromEntries(process.argv.slice(2).reduce((out,x,i,a)=>i%2===0?[...out,[x.slice(2),a[i+1]]]:out,[]));
const runtime=path.resolve(args.runtime), input=path.resolve(args.input), output=path.resolve(args.output);
const here=path.dirname(fileURLToPath(import.meta.url)),site=path.join(path.dirname(input),'motion-site');
fs.mkdirSync(site,{recursive:true});
for(const name of ['entry.ts','scene.ts','index.html'])fs.copyFileSync(path.join(here,name),path.join(site,name));
const modules=path.join(site,'node_modules');
if(!fs.existsSync(modules))fs.symlinkSync(path.join(runtime,'node_modules'),modules,'junction');
fs.writeFileSync(path.join(site,'package.json'),JSON.stringify({private:true,type:'module'}));
const data=JSON.parse(fs.readFileSync(input,'utf8'));
data.background='data:image/png;base64,'+fs.readFileSync(data.background).toString('base64');
fs.writeFileSync(path.join(site,'payload.json'),JSON.stringify(data));
const {createServer}=await import(pathToFileURL(path.join(runtime,'node_modules/vite/dist/node/index.js')).href);
const {chromium}=await import(pathToFileURL(path.join(runtime,'node_modules/playwright-core/index.mjs')).href);
const executable=process.env.CHROME_PATH || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge','/usr/bin/chromium','/usr/bin/chromium-browser','/usr/bin/google-chrome'].find(p=>fs.existsSync(p));
if(!executable)throw new Error('Chrome/Chromium not found; set CHROME_PATH');
const encoder=spawn('ffmpeg',['-loglevel','error','-y','-f','image2pipe','-vcodec','png','-framerate',String(data.fps),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p',output],{stdio:['pipe','ignore','pipe']});
let encodeError='',count=0,encoderCode;
encoder.stderr.on('data',chunk=>encodeError+=chunk.toString());
const encoded=new Promise(resolve=>encoder.on('close',code=>{encoderCode=code;resolve(code);}));
encoder.stdin.on('error',()=>{});
let server,browser;
try {
  const transport=(req,res)=>{
    const chunks=[];req.on('data',b=>chunks.push(b));
    req.on('end',()=>{
      if(encoderCode!==undefined){res.statusCode=500;res.end('Encoder stopped');return;}
      encoder.stdin.write(Buffer.concat(chunks),error=>{res.statusCode=error?500:200;if(!error)count++;res.end();});
    });
  };
  server=await createServer({configFile:false,root:site,cacheDir:path.join(site,'.vite'),logLevel:'warn',plugins:[{name:'physics-frame-transport',configureServer(s){s.middlewares.use('/__frame',transport);}}],server:{host:'127.0.0.1',port:0,hmr:false,fs:{allow:[site,runtime]}},optimizeDeps:{include:['@motion-canvas/core','@motion-canvas/2d']}});
  await server.listen();
  browser=await chromium.launch({headless:true,executablePath:executable,args:['--disable-dev-shm-usage']});
  const page=await browser.newPage({viewport:{width:1280,height:720}});
  page.on('console',msg=>{if(msg.type()==='error')process.stderr.write(msg.text()+'\n');});
  page.on('pageerror',error=>process.stderr.write(String(error)+'\n'));
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/index.html`,{waitUntil:'load'});
  await page.waitForFunction(()=>window.renderDone||window.renderError,null,{timeout:1800000});
  const error=await page.evaluate(()=>window.renderError);
  if(error)throw new Error(error);
  encoder.stdin.end();await encoded;
  if(encoderCode!==0)throw new Error('FFmpeg: '+encodeError);
  if(count!==data.page.frames)throw new Error(`Frame count ${count} != ${data.page.frames}`);
  console.log(JSON.stringify({renderer:'motion-canvas',frames:count,versions:data.engine_versions}));
} finally {
  if(browser)await browser.close();
  if(server)await server.close();
  if(encoderCode===undefined){encoder.stdin.destroy();encoder.kill('SIGTERM');await encoded;}
}
