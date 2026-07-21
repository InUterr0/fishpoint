#!/usr/bin/env node
import { spawnSync } from 'node:child_process';

const baseUrl = (process.argv[2] || 'http://127.0.0.1:4173').replace(/\/$/, '');
const cases = [
  { path: '/', text: '.logo-mark', background: '.logo-mark', label: 'logo mark' },
  { path: '/', text: '.btn-primary', background: '.btn-primary', label: 'primary CTA' },
  { path: '/', text: '.hero .hero-content .btn-secondary', background: '.hero .hero-content .btn-secondary', label: 'hero secondary CTA' },
  { path: '/aktualnosci/', text: '.news-catalog .blog-card a', background: '.news-catalog .blog-card', label: 'news card link' },
  { path: '/narzedzia/dobor-sprzetu.html', text: '.wizard-steps .step.current', background: '.wizard-steps .step.current', label: 'wizard current step' },
  { path: '/narzedzia/rozpoznaj-rybe.html', text: '.chip', background: '.chip', action: "document.querySelector('.chip')?.click()", label: 'selected chip' },
  { path: '/aktualnosci/jak-lowic-leszcza.html', text: '.article-next-step p', background: '.article-next-step', label: 'article next-step copy' },
  { path: '/aktualnosci/jak-lowic-leszcza.html', text: '.article-next-step a', background: '.article-next-step a', label: 'article next-step link' },
  { path: '/forum/', text: '.nav-cta', background: '.nav-cta', label: 'forum CTA' },
  { path: '/', text: '.analytics-settings', background: '.analytics-settings', label: 'analytics settings' },
  { path: '/', text: '.analytics-consent-accept', background: '.analytics-consent-accept', label: 'analytics consent' },
];

const jobs = [390, 1440].flatMap((width) =>
  ['light', 'dark'].flatMap((theme) =>
    [...new Set(cases.map((item) => item.path))].map((path) => ({
      width,
      theme,
      path,
      cases: cases.filter((item) => item.path === path),
    })),
  ),
);

const browserCode = `
(() => {
  document.querySelectorAll('iframe[data-contrast-regression]').forEach((node) => node.remove());
  const iframe = document.createElement('iframe');
  iframe.dataset.contrastRegression = '1';
  Object.assign(iframe.style, { position: 'fixed', left: '-3000px', top: '0', border: '0', height: '900px' });
  document.body.appendChild(iframe);

  const parseColor = (value) => {
    const parts = value.match(/[\\d.]+/g);
    return parts ? [+parts[0], +parts[1], +parts[2], parts[3] === undefined ? 1 : +parts[3]] : null;
  };
  const composite = (front, back) => {
    const alpha = front[3] + back[3] * (1 - front[3]);
    return [
      (front[0] * front[3] + back[0] * back[3] * (1 - front[3])) / alpha,
      (front[1] * front[3] + back[1] * back[3] * (1 - front[3])) / alpha,
      (front[2] * front[3] + back[2] * back[3] * (1 - front[3])) / alpha,
      alpha,
    ];
  };
  const luminance = (color) => {
    const channel = (value) => {
      value /= 255;
      return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * channel(color[0]) + 0.7152 * channel(color[1]) + 0.0722 * channel(color[2]);
  };
  const contrast = (left, right) => {
    const a = luminance(left);
    const b = luminance(right);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  };
  const load = (url) => new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('timeout ' + url)), 8000);
    iframe.onload = () => { clearTimeout(timer); resolve(); };
    iframe.src = url;
  });

  window.__fishpointContrast = {
    async run(job) {
      iframe.style.width = job.width + 'px';
      localStorage.setItem('fishpoint-theme', job.theme);
      await load(${JSON.stringify(baseUrl)} + job.path);
      const childDocument = iframe.contentDocument;
      const childWindow = childDocument.defaultView;
      childDocument.documentElement.classList.toggle('dark', job.theme === 'dark');
      await new Promise((resolve) => setTimeout(resolve, 250));

      const backgroundColors = (element) => {
        const style = childWindow.getComputedStyle(element);
        const gradientColors = [...style.backgroundImage.matchAll(/rgba?\\([^)]*\\)/g)]
          .map((match) => parseColor(match[0]))
          .filter((color) => color && color[3] > 0.01);
        if (gradientColors.length) return gradientColors;
        const own = parseColor(style.backgroundColor);
        if (own && own[3] >= 0.999) return [own];
        let parent = element.parentElement;
        while (parent) {
          const parentStyle = childWindow.getComputedStyle(parent);
          const parentColor = parseColor(parentStyle.backgroundColor);
          if (parentColor && parentColor[3] >= 0.999) {
            return own && own[3] ? [composite(own, parentColor)] : [parentColor];
          }
          const parentGradient = [...parentStyle.backgroundImage.matchAll(/rgba?\\([^)]*\\)/g)]
            .map((match) => parseColor(match[0]))
            .filter((color) => color && color[3] > 0.01);
          if (parentGradient.length) {
            const opaqueVariants = parentGradient.flatMap((color) => [
              composite(color, [0, 0, 0, 1]),
              composite(color, [255, 255, 255, 1]),
            ]);
            return own && own[3]
              ? opaqueVariants.map((background) => composite(own, background))
              : opaqueVariants;
          }
          parent = parent.parentElement;
        }
        return [];
      };

      const results = [];
      for (const item of job.cases) {
        if (item.action) childWindow.eval(item.action);
        await new Promise((resolve) => setTimeout(resolve, 180));
        const state = item.action ? '.active' : '';
        const textElement = childDocument.querySelector(item.text + state);
        const backgroundElement = childDocument.querySelector(item.background + state);
        if (!textElement || !backgroundElement) {
          results.push({ ...item, width: job.width, theme: job.theme, error: 'missing element' });
          continue;
        }
        const style = childWindow.getComputedStyle(textElement);
        const foreground = parseColor(style.color);
        const backgrounds = backgroundColors(backgroundElement);
        if (!foreground || !backgrounds.length) {
          results.push({ ...item, width: job.width, theme: job.theme, error: 'unresolved color' });
          continue;
        }
        const ratios = backgrounds.map((background) => contrast(composite(foreground, background), background));
        const ratio = Math.min(...ratios);
        const fontSize = parseFloat(style.fontSize);
        const required = fontSize >= 24 || (fontSize >= 18.66 && +style.fontWeight >= 700) ? 3 : 4.5;
        results.push({
          label: item.label,
          path: job.path,
          width: job.width,
          theme: job.theme,
          ratio: +ratio.toFixed(2),
          required,
          passed: ratio + 0.01 >= required,
        });
      }
      return results;
    },
  };
  return true;
})()
`;

const python = `
import json
new_tab(${JSON.stringify(baseUrl + '/')})
wait_for_load()
js(${JSON.stringify(browserCode)})
jobs = ${JSON.stringify(jobs)}
results = []
for job in jobs:
    results.extend(js('window.__fishpointContrast.run(' + json.dumps(job) + ')'))
failures = [item for item in results if item.get('error') or not item.get('passed')]
print(json.dumps({'checked': len(results), 'failures': failures}, ensure_ascii=False))
if failures:
    raise SystemExit(1)
`;

const result = spawnSync('bash', ['-lc', 'browser-harness'], {
  input: python,
  encoding: 'utf8',
  stdio: ['pipe', 'pipe', 'pipe'],
});
process.stdout.write(result.stdout || '');
process.stderr.write(result.stderr || '');
process.exit(result.status ?? 1);
