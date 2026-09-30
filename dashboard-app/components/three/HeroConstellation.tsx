"use client";

import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { Zap, Sparkles, ShieldCheck, CheckCircle2, ArrowRight } from "lucide-react";

interface QuerySimulation {
  prompt: string;
  isHit: boolean;
  tier: "L1" | "L2" | "MISS";
  similarity: number;
  latency: string;
  color: number;
}

const PRESET_QUERIES: QuerySimulation[] = [
  { prompt: "Explain binary search tree complexity", isHit: true, tier: "L2", similarity: 0.974, latency: "1.18ms", color: 0x06b6d4 },
  { prompt: "Calculate Q3 EBITDA guidance with 15% growth", isHit: true, tier: "L1", similarity: 1.0, latency: "0.34ms", color: 0x10b981 },
  { prompt: "Write quicksort algorithm in TypeScript", isHit: true, tier: "L2", similarity: 0.942, latency: "1.25ms", color: 0x6366f1 },
  { prompt: "Generate random UUIDv4 string for session", isHit: false, tier: "MISS", similarity: 0.21, latency: "842ms", color: 0xf43f5e },
];

export default function HeroConstellation() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeQuery, setActiveQuery] = useState<QuerySimulation | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const triggerSimulationRef = useRef<((sim: QuerySimulation) => void) | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // --- Scene Setup ---
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x07090e, 0.007);

    const camera = new THREE.PerspectiveCamera(58, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(0, 0, 92);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // --- Structured Semantic Clusters (4 Domains) ---
    const CLUSTER_CONFIGS = [
      { name: "L1_EXACT_HASH", center: new THREE.Vector3(-34, 16, 10), color: new THREE.Color("#10b981"), count: 70, radius: 14 },
      { name: "L2_CODE_EMBEDDINGS", center: new THREE.Vector3(30, -12, 12), color: new THREE.Color("#6366f1"), count: 110, radius: 22 },
      { name: "L2_FINANCE_SEMANTICS", center: new THREE.Vector3(26, 22, -10), color: new THREE.Color("#06b6d4"), count: 90, radius: 18 },
      { name: "GUARDRAIL_ARBITER", center: new THREE.Vector3(-26, -20, -5), color: new THREE.Color("#a855f7"), count: 80, radius: 16 },
    ];

    const totalParticles = CLUSTER_CONFIGS.reduce((acc, c) => acc + c.count, 0) + 120; // + ambient background particles
    const positions = new Float32Array(totalParticles * 3);
    const basePositions = new Float32Array(totalParticles * 3);
    const colors = new Float32Array(totalParticles * 3);
    const sizes = new Float32Array(totalParticles);

    let pIdx = 0;

    // Build structured domain clusters
    CLUSTER_CONFIGS.forEach((cluster) => {
      for (let i = 0; i < cluster.count; i++) {
        const i3 = pIdx * 3;
        // Gaussian/spherical distribution around cluster center
        const u = Math.random();
        const v = Math.random();
        const theta = u * 2.0 * Math.PI;
        const phi = Math.acos(2.0 * v - 1.0);
        const r = Math.cbrt(Math.random()) * cluster.radius;
        const sinPhi = Math.sin(phi);

        const x = cluster.center.x + r * sinPhi * Math.cos(theta);
        const y = cluster.center.y + r * sinPhi * Math.sin(theta);
        const z = cluster.center.z + r * Math.cos(phi);

        positions[i3] = x;
        positions[i3 + 1] = y;
        positions[i3 + 2] = z;

        basePositions[i3] = x;
        basePositions[i3 + 1] = y;
        basePositions[i3 + 2] = z;

        colors[i3] = cluster.color.r;
        colors[i3 + 1] = cluster.color.g;
        colors[i3 + 2] = cluster.color.b;

        sizes[pIdx] = 2.5 + Math.random() * 2.0;
        pIdx++;
      }
    });

    // Add ambient background depth stars
    for (let i = 0; i < 120; i++) {
      const i3 = pIdx * 3;
      const x = (Math.random() - 0.5) * 160;
      const y = (Math.random() - 0.5) * 110;
      const z = (Math.random() - 0.5) * 80 - 20;

      positions[i3] = x;
      positions[i3 + 1] = y;
      positions[i3 + 2] = z;

      basePositions[i3] = x;
      basePositions[i3 + 1] = y;
      basePositions[i3 + 2] = z;

      colors[i3] = 0.35;
      colors[i3 + 1] = 0.45;
      colors[i3 + 2] = 0.7;

      sizes[pIdx] = 1.4 + Math.random() * 1.5;
      pIdx++;
    }

    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    particleGeometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    particleGeometry.setAttribute("size", new THREE.BufferAttribute(sizes, 1));

    // Particle texture
    const canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext("2d")!;
    const radGrad = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    radGrad.addColorStop(0, "rgba(255, 255, 255, 1)");
    radGrad.addColorStop(0.25, "rgba(165, 180, 252, 0.9)");
    radGrad.addColorStop(0.6, "rgba(99, 102, 241, 0.35)");
    radGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = radGrad;
    ctx.fillRect(0, 0, 64, 64);
    const particleTexture = new THREE.CanvasTexture(canvas);

    const particleMaterial = new THREE.PointsMaterial({
      size: 3.5,
      map: particleTexture,
      transparent: true,
      vertexColors: true,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const particleSystem = new THREE.Points(particleGeometry, particleMaterial);
    scene.add(particleSystem);

    // --- Pre-calculated Fixed Cluster Highway Lines (No O(N^2) CPU overhead) ---
    const clusterLineIndices: number[] = [];
    // Connect nearest nodes within each cluster
    let offset = 0;
    CLUSTER_CONFIGS.forEach((cluster) => {
      for (let i = 0; i < cluster.count; i++) {
        for (let j = i + 1; j < Math.min(i + 5, cluster.count); j++) {
          clusterLineIndices.push(offset + i, offset + j);
        }
      }
      offset += cluster.count;
    });

    // Inter-cluster backbone bridge filaments
    clusterLineIndices.push(
      0, 75,
      10, 185,
      72, 190,
      180, 275,
      280, 5
    );

    const linePositions = new Float32Array(clusterLineIndices.length * 3);
    const lineColors = new Float32Array(clusterLineIndices.length * 3);

    for (let i = 0; i < clusterLineIndices.length; i++) {
      const pId = clusterLineIndices[i];
      const i3 = i * 3;
      const src3 = pId * 3;
      linePositions[i3] = basePositions[src3];
      linePositions[i3 + 1] = basePositions[src3 + 1];
      linePositions[i3 + 2] = basePositions[src3 + 2];

      lineColors[i3] = colors[src3] * 0.7;
      lineColors[i3 + 1] = colors[src3 + 1] * 0.7;
      lineColors[i3 + 2] = colors[src3 + 2] * 0.7;
    }

    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", new THREE.BufferAttribute(linePositions, 3));
    lineGeo.setAttribute("color", new THREE.BufferAttribute(lineColors, 3));

    const lineMat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.3,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const highwayLines = new THREE.LineSegments(lineGeo, lineMat);
    scene.add(highwayLines);

    // --- Cluster Centroid Glowing Beacons ---
    const centroidGroup = new THREE.Group();
    scene.add(centroidGroup);

    const centroidMeshes: { mesh: THREE.Mesh; halo: THREE.Mesh; basePos: THREE.Vector3 }[] = [];

    CLUSTER_CONFIGS.forEach((c) => {
      const coreGeo = new THREE.SphereGeometry(1.6, 24, 24);
      const coreMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
      const core = new THREE.Mesh(coreGeo, coreMat);
      core.position.copy(c.center);

      const haloGeo = new THREE.SphereGeometry(3.2, 16, 16);
      const haloMat = new THREE.MeshBasicMaterial({
        color: c.color,
        wireframe: true,
        transparent: true,
        opacity: 0.55,
      });
      const halo = new THREE.Mesh(haloGeo, haloMat);
      core.add(halo);

      centroidGroup.add(core);
      centroidMeshes.push({ mesh: core, halo, basePos: c.center.clone() });
    });

    // --- Pre-Allocated Query Photon Wave Beam ---
    const beamCurvePoints = 30;
    const beamPositions = new Float32Array(beamCurvePoints * 3);
    const beamGeo = new THREE.BufferGeometry();
    beamGeo.setAttribute("position", new THREE.BufferAttribute(beamPositions, 3));

    const beamMat = new THREE.LineBasicMaterial({
      color: 0x22d3ee,
      linewidth: 2,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
    });
    const queryBeam = new THREE.Line(beamGeo, beamMat);
    scene.add(queryBeam);

    // Reusable Pulse Ring Pool (Zero GC allocation during interaction)
    const pulseRingGeo = new THREE.RingGeometry(1, 1.6, 32);
    const pulseRingMat = new THREE.MeshBasicMaterial({
      color: 0x06b6d4,
      transparent: true,
      opacity: 0,
      side: THREE.DoubleSide,
    });
    const pulseRing = new THREE.Mesh(pulseRingGeo, pulseRingMat);
    pulseRing.visible = false;
    scene.add(pulseRing);

    let pulseState = { active: false, scale: 1, maxScale: 40, opacity: 0, x: 0, y: 0, z: 0 };

    // --- Simulation Trigger Function ---
    const triggerSimulation = (sim: QuerySimulation) => {
      setActiveQuery(sim);
      setIsSimulating(true);

      const startPos = new THREE.Vector3(0, -45, 20); // Gateway ingestion point
      const targetCluster = sim.tier === "L1" ? CLUSTER_CONFIGS[0].center : CLUSTER_CONFIGS[1].center;
      const targetPos = sim.isHit ? targetCluster : new THREE.Vector3(50, 40, -30); // LLM upstream cloud on miss

      // Update beam geometry
      beamMat.color.setHex(sim.color);
      beamMat.opacity = 1.0;

      const curve = new THREE.QuadraticBezierCurve3(
        startPos,
        new THREE.Vector3((startPos.x + targetPos.x) / 2, (startPos.y + targetPos.y) / 2 + 15, 25),
        targetPos
      );

      const pts = curve.getPoints(beamCurvePoints - 1);
      const bPos = beamGeo.attributes.position as THREE.BufferAttribute;
      const bArr = bPos.array as Float32Array;

      for (let i = 0; i < pts.length; i++) {
        bArr[i * 3] = pts[i].x;
        bArr[i * 3 + 1] = pts[i].y;
        bArr[i * 3 + 2] = pts[i].z;
      }
      bPos.needsUpdate = true;

      // Trigger target explosion ring
      pulseRingMat.color.setHex(sim.color);
      pulseRing.position.copy(targetPos);
      pulseRing.visible = true;
      pulseState = { active: true, scale: 1, maxScale: 38, opacity: 1.0, x: targetPos.x, y: targetPos.y, z: targetPos.z };

      setTimeout(() => {
        setIsSimulating(false);
      }, 2500);
    };

    triggerSimulationRef.current = triggerSimulation;

    // --- Mouse Parallax & Gravitational Drift ---
    const mouse = { x: 0, y: 0, targetX: 0, targetY: 0 };
    const handleMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      mouse.targetX = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.targetY = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
    };

    const handleClick = (e: MouseEvent) => {
      const randomQuery = PRESET_QUERIES[Math.floor(Math.random() * PRESET_QUERIES.length)];
      triggerSimulation(randomQuery);
    };

    window.addEventListener("mousemove", handleMouseMove);
    container.addEventListener("click", handleClick);

    const handleResize = () => {
      if (!container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener("resize", handleResize);

    // --- High-Performance Animation Loop ---
    let frameId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      frameId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Smooth mouse lerp
      mouse.x += (mouse.targetX - mouse.x) * 0.04;
      mouse.y += (mouse.targetY - mouse.y) * 0.04;

      // Rotate entire coordinate space with subtle inertia
      const rotY = elapsed * 0.03 + mouse.x * 0.25;
      const rotX = elapsed * 0.015 + mouse.y * 0.15;

      particleSystem.rotation.y = rotY;
      particleSystem.rotation.x = rotX;
      highwayLines.rotation.y = rotY;
      highwayLines.rotation.x = rotX;
      centroidGroup.rotation.y = rotY;
      centroidGroup.rotation.x = rotX;

      // Animate centroid pulsating wireframe halos
      centroidMeshes.forEach((c, idx) => {
        c.halo.rotation.y += 0.02 * (idx % 2 === 0 ? 1 : -1);
        c.halo.rotation.x += 0.015;
        const scale = 1.0 + Math.sin(elapsed * 2.5 + idx * 1.5) * 0.15;
        c.halo.scale.set(scale, scale, scale);
      });

      // Animate beam fade
      if (beamMat.opacity > 0) {
        beamMat.opacity -= 0.012;
      }

      // Animate pulse ring
      if (pulseState.active) {
        pulseState.scale += 0.8;
        pulseState.opacity -= 0.02;
        pulseRing.scale.set(pulseState.scale, pulseState.scale, 1);
        pulseRingMat.opacity = Math.max(0, pulseState.opacity);

        if (pulseState.opacity <= 0 || pulseState.scale >= pulseState.maxScale) {
          pulseState.active = false;
          pulseRing.visible = false;
        }
      }

      renderer.render(scene, camera);
    };

    animate();

    // Auto-fire a demo simulation on launch
    const timer = setTimeout(() => {
      triggerSimulation(PRESET_QUERIES[0]);
    }, 1200);

    return () => {
      clearTimeout(timer);
      cancelAnimationFrame(frameId);
      window.removeEventListener("mousemove", handleMouseMove);
      container.removeEventListener("click", handleClick);
      window.removeEventListener("resize", handleResize);

      if (container && renderer.domElement) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
      particleGeometry.dispose();
      particleMaterial.dispose();
      lineGeo.dispose();
      lineMat.dispose();
      beamGeo.dispose();
      beamMat.dispose();
      pulseRingGeo.dispose();
      pulseRingMat.dispose();
    };
  }, []);

  return (
    <div className="absolute inset-0 w-full h-full overflow-hidden select-none">
      {/* 3D WebGL Canvas */}
      <div ref={containerRef} className="w-full h-full cursor-crosshair" />

      {/* Floating Query Execution HUD Badge */}
      {activeQuery && (
        <div className="absolute top-24 right-6 z-30 pointer-events-auto bg-slate-950/85 backdrop-blur-xl border border-slate-800 p-4 shadow-2xl max-w-sm hidden sm:block animate-in fade-in slide-in-from-right duration-300">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-2 mb-2.5">
            <div className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${activeQuery.isHit ? "bg-emerald-400 animate-pulse" : "bg-rose-400"}`} />
              <span className="text-xs font-mono font-bold text-slate-200 uppercase tracking-wider">
                {activeQuery.isHit ? `GATEWAY ${activeQuery.tier} CACHE HIT` : "UPSTREAM FALLBACK (MISS)"}
              </span>
            </div>
            <span className={`text-[10px] font-mono px-2 py-0.5 font-bold ${activeQuery.isHit ? "bg-emerald-950 text-emerald-300 border border-emerald-800" : "bg-rose-950 text-rose-300 border border-rose-800"}`}>
              {activeQuery.latency}
            </span>
          </div>

          <p className="text-[11px] font-mono text-slate-300 line-clamp-2 mb-3 bg-slate-900/90 p-2 border border-slate-800/60">
            &ldquo;{activeQuery.prompt}&rdquo;
          </p>

          <div className="grid grid-cols-2 gap-2 text-[10px] font-mono text-slate-400">
            <div>SIMILARITY: <span className="text-cyan-300 font-bold">{(activeQuery.similarity * 100).toFixed(1)}%</span></div>
            <div>COMPUTE SAVED: <span className="text-emerald-300 font-bold">{activeQuery.isHit ? "100%" : "0%"}</span></div>
          </div>
        </div>
      )}

      {/* Interactive Trigger Bar at bottom of Hero */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 pointer-events-auto bg-slate-950/80 backdrop-blur-md border border-slate-800/80 px-4 py-2 text-xs font-mono text-slate-300 shadow-2xl">
        <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mr-1">SIMULATE:</span>
        {PRESET_QUERIES.map((q, idx) => (
          <button
            key={idx}
            onClick={() => triggerSimulationRef.current && triggerSimulationRef.current(q)}
            className={`px-2.5 py-1 text-[11px] border transition-all ${activeQuery?.prompt === q.prompt ? "bg-indigo-950/80 border-indigo-500 text-indigo-200 shadow-[0_0_10px_rgba(99,102,241,0.3)]" : "bg-slate-900/50 border-slate-800 text-slate-400 hover:text-slate-200 hover:border-slate-700"}`}
          >
            {q.tier === "L1" ? "L1 Hash" : q.tier === "L2" ? "L2 Semantic" : "Miss"}
          </button>
        ))}
      </div>
    </div>
  );
}
