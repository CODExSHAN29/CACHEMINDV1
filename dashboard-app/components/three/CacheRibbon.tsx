"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

/** Abstract geometry, never a visualization of customer embeddings. */
export default function CacheRibbon({ tension = 0.437, mode = 0 }: { tension?: number; mode?: number }) {
  const host = useRef<HTMLDivElement>(null);
  const parameters = useRef({ tension, mode });
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => { parameters.current = { tension, mode }; }, [tension, mode]);

  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: "low-power" }); }
    catch { setUnavailable(true); return; }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    element.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 30);
    camera.position.z = 6;
    const group = new THREE.Group();
    scene.add(group);
    const count = window.innerWidth < 768 ? 48 : 84;
    const segments = 160;
    const lines: THREE.Line[] = [];
    for (let i = 0; i < count; i++) {
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array((segments + 1) * 3), 3));
      const material = new THREE.LineBasicMaterial({ color: i > count * 0.56 ? 0x2563eb : 0xb8becb, transparent: true, opacity: i > count * 0.56 ? 0.82 : 0.18 + i / count * 0.45 });
      const line = new THREE.Line(geometry, material);
      line.frustumCulled = false;
      lines.push(line); group.add(line);
    }
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let visible = true, lost = false, frame = 0, last = 0, phase = 0, previous = "";
    let dirty = true;
    const pointer = { x: 0, y: 0 };
    const resize = () => {
      const { width, height } = element.getBoundingClientRect();
      renderer.setSize(width, height); dirty = true;
      camera.aspect = width / Math.max(height, 1); camera.updateProjectionMatrix();
      group.scale.setScalar(width < 600 ? 0.85 : 1.45);
    };
    const observer = new ResizeObserver(resize); observer.observe(element); resize();
    const visibility = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; });
    visibility.observe(element);
    const onPointer = (event: PointerEvent) => {
      const bounds = element.getBoundingClientRect();
      pointer.x = (event.clientX - bounds.left) / bounds.width - 0.5;
      pointer.y = (event.clientY - bounds.top) / bounds.height - 0.5;
    };
    element.addEventListener("pointermove", onPointer);
    const onLost = (event: Event) => { event.preventDefault(); lost = true; setUnavailable(true); };
    const onRestored = () => { lost = false; setUnavailable(false); };
    renderer.domElement.addEventListener("webglcontextlost", onLost);
    renderer.domElement.addEventListener("webglcontextrestored", onRestored);
    const draw = (now: number) => {
      frame = requestAnimationFrame(draw);
      if (lost || !visible || document.hidden || now - last < 33) return;
      const delta = Math.min((now - last) / 1000, 0.05); last = now;
      if (!motion.matches) phase += delta * 0.14;
      const { tension: value, mode: current } = parameters.current;
      const signature = `${value}/${current}`;
      if (motion.matches && !dirty && previous === signature) return;
      previous = signature; dirty = false;
      for (let i = 0; i < count; i++) {
        const offset = i / count - 0.5;
        const attribute = lines[i].geometry.getAttribute("position") as THREE.BufferAttribute;
        for (let j = 0; j <= segments; j++) {
          const t = j / segments * Math.PI * 2;
          const wave = current === 1 ? Math.sin(t * 3.2 + phase + offset * 6.5) : current === 2 ? Math.sin(t * 1.2 + phase + offset * 2.2) * 0.45 : Math.sin(t * 2 + phase + offset * 4);
          const secondary = Math.cos(t * (current === 1 ? 4.1 : current === 2 ? 1.8 : 3) - phase * 0.8 + offset * 3);
          const twist = Math.sin(t + offset * 2.5) * value;
          attribute.setXYZ(j, Math.cos(t) * 1.1 + wave * 0.35 + twist * 0.4, -(Math.sin(t * 1.5) * 0.85 + secondary * 0.4 + offset * 1.2) * 0.8, Math.sin(t * 2 + wave) * 0.5 + offset);
        }
        attribute.needsUpdate = true;
      }
      group.rotation.y = motion.matches ? 0.1 : phase * 0.2 + pointer.x * 0.2;
      group.rotation.x = motion.matches ? 0 : pointer.y * 0.12;
      group.position.x = camera.aspect > 1.2 ? 0.5 : 0.15;
      renderer.render(scene, camera);
    };
    frame = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(frame); observer.disconnect(); visibility.disconnect();
      element.removeEventListener("pointermove", onPointer);
      renderer.domElement.removeEventListener("webglcontextlost", onLost);
      renderer.domElement.removeEventListener("webglcontextrestored", onRestored);
      lines.forEach(line => { line.geometry.dispose(); (line.material as THREE.Material).dispose(); });
      renderer.dispose(); renderer.domElement.remove();
    };
  }, []);
  return <div ref={host} className="cache-ribbon" aria-hidden="true">{unavailable && <span className="ribbon-unavailable">GEOMETRY UNAVAILABLE / WEBGL</span>}</div>;
}
