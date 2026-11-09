import {Circle, Img, Line, Node, makeScene2D} from '@motion-canvas/2d';
import {createSignal, tween} from '@motion-canvas/core';

// Stroke order and analytic model coordinates are supplied by the common course compiler.
export default makeScene2D(function* (view) {
  const data = (window as any).courseData;
  const page = data.page;
  const clock = createSignal(0);
  const focus = () => {
    for (const event of (page.focus || [])) {
      const transition = event.transition;
      if (clock() >= event.start - transition && clock() <= event.end + transition) {
        const rise = Math.max(0, Math.min(1, (clock() - event.start + transition) / transition));
        const fall = Math.max(0, Math.min(1, (event.end + transition - clock()) / transition));
        let amount = Math.min(rise, fall); amount = amount * amount * (3 - 2 * amount);
        const [x, y, w, h] = event.rect;
        return {zoom: 1 + (event.zoom - 1) * amount, center: [x + w / 2 - 640, y + h / 2 - 360]};
      }
    }
    return {zoom: 1, center: [0, 0]};
  };
  const camera = new Node({
    scale: () => focus().zoom,
    position: () => {
      const state = focus(), delta = state.zoom - 1;
      return [-state.center[0] * delta, -state.center[1] * delta];
    },
  });
  const root = new Node({position: [-640, -360]});
  view.add(camera);camera.add(root);
  root.add(new Img({src: data.background, position: [640, 360], width: 1280, height: 720}));
  const dynamic = data.dynamic_frames || [];
  const frame = () => dynamic[Math.min(dynamic.length - 1, Math.floor((clock() + 1e-8) * data.fps))] || [];
  const maxCount = dynamic.reduce((n: number, f: any[]) => Math.max(n, f.length), 0);
  for (let i = 0; i < maxCount; i++) {
    root.add(new Line({
      points: () => frame()[i]?.points || [[0, 0], [0.001, 0]],
      stroke: () => frame()[i]?.color || '#29333c',
      lineWidth: () => frame()[i]?.width || 2,
      opacity: () => frame()[i] ? 1 : 0,
      lineCap: 'round', lineJoin: 'round',
    }));
  }
  for (const stroke of page.strokes) {
    root.add(new Line({
      points: stroke.points, stroke: stroke.color, lineWidth: stroke.width,
      lineCap: 'round', lineJoin: 'round',
      opacity: () => clock() >= stroke.start ? 1 : 0,
      end: () => Math.max(0, Math.min(1, (clock() - stroke.start) / (stroke.end - stroke.start))),
    }));
  }
  const active = () => page.strokes.find((s: any) => s.start <= clock() && s.end > clock());
  const cursorPosition = () => {
    const s = active();
    if (!s) return [0, 0];
    let length = 0;
    for (let i = 1; i < s.points.length; i++) length += Math.hypot(s.points[i][0] - s.points[i-1][0], s.points[i][1] - s.points[i-1][1]);
    let remaining = length * (clock() - s.start) / (s.end - s.start);
    for (let i = 1; i < s.points.length; i++) {
      const a = s.points[i-1], b = s.points[i];
      const span = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (remaining <= span) {
        const f = span ? remaining / span : 0;
        return [a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])];
      }
      remaining -= span;
    }
    return s.points[s.points.length - 1];
  };
  root.add(new Circle({width: 10, height: 10, fill: '#355c49', stroke: '#fffef9', lineWidth: 2,
    position: cursorPosition, opacity: () => active() ? 1 : 0}));
  const duration = page.frames / data.fps + 1 / data.fps;
  yield* tween(duration, value => clock(value * duration));
});
