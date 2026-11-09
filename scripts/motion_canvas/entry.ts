import {bootstrap, MetaFile, ObjectMetaField, Renderer, ValueDispatcher, Vector2} from '@motion-canvas/core';

declare global { interface Window {courseData: any; renderDone?: boolean; renderError?: string;} }

async function run() {
  window.courseData = await (await fetch('/payload.json')).json();
  const data = window.courseData;
  const {default: scene} = await import('./scene');
  const description = {...scene, name: 'notebook', onReplaced: new ValueDispatcher(scene.config)};
  let frames = 0;
  class PipeExporter {
    static id = 'physics-png-pipe';
    static displayName = 'Physics PNG Pipe';
    static meta() {return new ObjectMetaField('Physics', {});}
    static async create() {return new PipeExporter();}
    async handleFrame(canvas: HTMLCanvasElement, frame: number) {
      if (frame >= data.page.frames) return;
      const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(b => b ? resolve(b) : reject(new Error('PNG encoding failed')), 'image/png'));
      const response = await fetch('/__frame', {method: 'POST', body: blob});
      if (!response.ok) throw new Error('Frame transport failed');
      frames++;
    }
  }
  const plugin = {name: 'physics-exporter', exporters: () => [PipeExporter]};
  const project = bootstrap('physics-notebook', {core:'3.17.2', two:'3.17.2', ui:null, vitePlugin:null}, [plugin], {scenes:[description]}, new MetaFile('project', false), new MetaFile('settings', false));
  project.logger.onLogged.subscribe((event: any) => {
    if (event.level === 'error') console.error(event.message, event.stack || '');
  });
  const renderer = new Renderer(project);
  let result = -1;
  renderer.onFinished.subscribe(value => result = value);
  await renderer.render({name:'page', size:new Vector2(1280,720), resolutionScale:data.width/1280,
    colorSpace:'srgb', background:'#e9ece7', fps:data.fps,
    range:[0,(data.page.frames-1)/data.fps], exporter:{name:PipeExporter.id,options:{}}});
  if (result !== 0 || frames !== data.page.frames) throw new Error(`Motion Canvas export result=${result}; frames=${frames}, expected=${data.page.frames}`);
  window.renderDone = true;
}
run().catch(error => {console.error(error); window.renderError = String(error.stack || error);});
