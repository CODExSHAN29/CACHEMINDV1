"use client";

import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { Database, Search, Sliders, Layers, RefreshCw, ZoomIn, Info, ShieldCheck } from "lucide-react";

export interface VectorPoint {
  id: string;
  prompt: string;
  model: string;
  similarity: number;
  cluster: "Code & Algorithms" | "Finance & Metrics" | "Bio & Science" | "System Prompts";
  hash: string;
  ttl: number;
  pos: [number, number, number];
  tokensSaved: number;
}

export const SAMPLE_VECTORS: VectorPoint[] = [
  // Cluster 1: Code & Algorithms (Indigo)
  { id: "vec-1", prompt: "Explain binary search tree complexity in Python", model: "gpt-4o", similarity: 0.982, cluster: "Code & Algorithms", hash: "sha256:a8f902c3", ttl: 86400, pos: [-32, 18, 14], tokensSaved: 420 },
  { id: "vec-2", prompt: "Write quicksort in TypeScript with generic comparator", model: "claude-3-5-sonnet", similarity: 0.965, cluster: "Code & Algorithms", hash: "sha256:b7e21190", ttl: 86400, pos: [-38, 24, 10], tokensSaved: 680 },
  { id: "vec-3", prompt: "How does asyncio event loop work in Python 3.12?", model: "gpt-4o-mini", similarity: 0.941, cluster: "Code & Algorithms", hash: "sha256:c3d4e5f6", ttl: 86400, pos: [-26, 12, 22], tokensSaved: 510 },
  { id: "vec-4", prompt: "Convert UTC timestamps to ISO-8601 string in Rust", model: "claude-3-5-sonnet", similarity: 0.973, cluster: "Code & Algorithms", hash: "sha256:7c8d9e0f", ttl: 86400, pos: [-40, 16, 18], tokensSaved: 310 },
  { id: "vec-5", prompt: "Implement Redis LRU eviction policy in Go", model: "gpt-4o", similarity: 0.915, cluster: "Code & Algorithms", hash: "sha256:1f2e3d4c", ttl: 86400, pos: [-28, 28, 6], tokensSaved: 740 },

  // Cluster 2: Finance & Metrics (Emerald)
  { id: "vec-6", prompt: "Calculate Q3 EBITDA guidance with 15% revenue growth", model: "gpt-4o", similarity: 0.991, cluster: "Finance & Metrics", hash: "sha256:d4e5f6a7", ttl: 300, pos: [30, -20, -12], tokensSaved: 890 },
  { id: "vec-7", prompt: "Summarize Federal Reserve interest rate forecast", model: "gpt-4o", similarity: 0.954, cluster: "Finance & Metrics", hash: "sha256:e5f6a7b8", ttl: 600, pos: [36, -14, -18], tokensSaved: 620 },
  { id: "vec-8", prompt: "What is Black-Scholes option pricing formula delta?", model: "claude-3-5-sonnet", similarity: 0.978, cluster: "Finance & Metrics", hash: "sha256:f6a7b8c9", ttl: 300, pos: [24, -26, -8], tokensSaved: 950 },
  { id: "vec-9", prompt: "Analyze portfolio beta vs S&P 500 benchmark volatility", model: "gpt-4o", similarity: 0.962, cluster: "Finance & Metrics", hash: "sha256:8d9e0f1a", ttl: 300, pos: [34, -22, -6], tokensSaved: 480 },

  // Cluster 3: Bio & Science (Cyan)
  { id: "vec-10", prompt: "Mechanism of action for mRNA vaccines and lipid caps", model: "gpt-4o", similarity: 0.938, cluster: "Bio & Science", hash: "sha256:1a2b3c4d", ttl: 604800, pos: [20, 28, 24], tokensSaved: 1120 },
  { id: "vec-11", prompt: "CRISPR-Cas9 guide RNA off-target cleavage prevention", model: "claude-3-5-sonnet", similarity: 0.957, cluster: "Bio & Science", hash: "sha256:2b3c4d5e", ttl: 604800, pos: [28, 32, 18], tokensSaved: 1350 },
  { id: "vec-12", prompt: "Protein folding tertiary structure prediction via AlphaFold", model: "gpt-4o", similarity: 0.949, cluster: "Bio & Science", hash: "sha256:3c4d5e6f", ttl: 604800, pos: [16, 22, 30], tokensSaved: 980 },

  // Cluster 4: System Directives & Guardrails (Amber)
  { id: "vec-13", prompt: "You are a helpful coding assistant that returns strict JSON", model: "system-directive", similarity: 1.0, cluster: "System Prompts", hash: "sha256:9z8y7x6w", ttl: 2592000, pos: [-18, -24, 28], tokensSaved: 250 },
  { id: "vec-14", prompt: "Do not provide dangerous or unauthorized vulnerability exploits", model: "guardrail-arbiter", similarity: 0.999, cluster: "System Prompts", hash: "sha256:8y7x6w5v", ttl: 2592000, pos: [-24, -28, 22], tokensSaved: 180 },
  { id: "vec-15", prompt: "Format all mathematical expressions in LaTeX syntax", model: "system-directive", similarity: 0.985, cluster: "System Prompts", hash: "sha256:7x6w5v4u", ttl: 2592000, pos: [-14, -20, 32], tokensSaved: 210 },
];

const CLUSTER_COLORS: Record<string, { hex: number; tailwind: string; border: string; bg: string }> = {
  "Code & Algorithms": { hex: 0x6366f1, tailwind: "text-indigo-400", border: "border-indigo-500/50", bg: "bg-indigo-950/80" },
  "Finance & Metrics": { hex: 0x10b981, tailwind: "text-emerald-400", border: "border-emerald-500/50", bg: "bg-emerald-950/80" },
  "Bio & Science": { hex: 0x06b6d4, tailwind: "text-cyan-400", border: "border-cyan-500/50", bg: "bg-cyan-950/80" },
  "System Prompts": { hex: 0xf59e0b, tailwind: "text-amber-400", border: "border-amber-500/50", bg: "bg-amber-950/80" },
};

export default function VectorClusterVisualizer({ className = "" }: { className?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [selectedPoint, setSelectedPoint] = useState<VectorPoint | null>(SAMPLE_VECTORS[0]);
  const [hoveredPoint, setHoveredPoint] = useState<VectorPoint | null>(null);
  const [similarityThreshold, setSimilarityThreshold] = useState<number>(0.92);
  const [searchFilter, setSearchFilter] = useState<string>("");
  const [activeCluster, setActiveCluster] = useState<string>("ALL");

  // Ref to pass dynamic threshold to WebGL render cycle
  const thresholdRef = useRef(similarityThreshold);
  useEffect(() => {
    thresholdRef.current = similarityThreshold;
  }, [similarityThreshold]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Scene & Camera
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x07090e, 0.006);

    const camera = new THREE.PerspectiveCamera(54, container.clientWidth / container.clientHeight, 0.1, 1000);
    camera.position.set(0, 5, 88);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Bounding Coordinate Cage
    const cageGeo = new THREE.BoxGeometry(94, 76, 76);
    const cageEdges = new THREE.EdgesGeometry(cageGeo);
    const cageMat = new THREE.LineBasicMaterial({ color: 0x1e293b, transparent: true, opacity: 0.35 });
    const cageBox = new THREE.LineSegments(cageEdges, cageMat);
    scene.add(cageBox);

    // Node Group
    const nodesGroup = new THREE.Group();
    scene.add(nodesGroup);

    // Render 3D Vector Nodes
    const pointMeshes: { mesh: THREE.Mesh; halo: THREE.Mesh; data: VectorPoint }[] = [];

    SAMPLE_VECTORS.forEach((vec) => {
      const col = CLUSTER_COLORS[vec.cluster]?.hex || 0x6366f1;

      // Solid Core Sphere
      const coreGeo = new THREE.SphereGeometry(1.8, 20, 20);
      const coreMat = new THREE.MeshBasicMaterial({ color: col });
      const coreMesh = new THREE.Mesh(coreGeo, coreMat);
      coreMesh.position.set(...vec.pos);

      // Glowing Halo Shell
      const haloGeo = new THREE.SphereGeometry(2.6, 16, 16);
      const haloMat = new THREE.MeshBasicMaterial({
        color: col,
        wireframe: true,
        transparent: true,
        opacity: 0.45,
      });
      const haloMesh = new THREE.Mesh(haloGeo, haloMat);
      coreMesh.add(haloMesh);

      nodesGroup.add(coreMesh);
      pointMeshes.push({ mesh: coreMesh, halo: haloMesh, data: vec });
    });

    // Dynamic Cosine Similarity Inter-Node Lines
    const maxLines = 120;
    const linePositions = new Float32Array(maxLines * 6);
    const lineColors = new Float32Array(maxLines * 6);
    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", new THREE.BufferAttribute(linePositions, 3));
    lineGeo.setAttribute("color", new THREE.BufferAttribute(lineColors, 3));

    const lineMat = new THREE.LineBasicMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.45,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const connectionLines = new THREE.LineSegments(lineGeo, lineMat);
    nodesGroup.add(connectionLines);

    // Interactive Drag / Orbit Mechanics with Inertia
    let isDragging = false;
    let prevMouse = { x: 0, y: 0 };
    let velocity = { x: 0, y: 0 };
    const mouse2D = new THREE.Vector2(-100, -100);
    const raycaster = new THREE.Raycaster();

    const handlePointerDown = (e: MouseEvent) => {
      isDragging = true;
      prevMouse = { x: e.clientX, y: e.clientY };
    };

    const handlePointerMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      mouse2D.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse2D.y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);

      if (isDragging) {
        const dx = e.clientX - prevMouse.x;
        const dy = e.clientY - prevMouse.y;
        velocity.x = dx * 0.006;
        velocity.y = dy * 0.006;

        nodesGroup.rotation.y += velocity.x;
        nodesGroup.rotation.x += velocity.y;

        prevMouse = { x: e.clientX, y: e.clientY };
      }
    };

    const handlePointerUp = () => {
      isDragging = false;
    };

    const handleClick = () => {
      raycaster.setFromCamera(mouse2D, camera);
      const meshes = pointMeshes.map((p) => p.mesh);
      const intersects = raycaster.intersectObjects(meshes, false);

      if (intersects.length > 0) {
        const found = pointMeshes.find((p) => p.mesh === intersects[0].object);
        if (found) {
          setSelectedPoint(found.data);
        }
      }
    };

    container.addEventListener("mousedown", handlePointerDown);
    window.addEventListener("mousemove", handlePointerMove);
    window.addEventListener("mouseup", handlePointerUp);
    container.addEventListener("click", handleClick);

    const handleResize = () => {
      if (!container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener("resize", handleResize);

    // Animation Loop
    let frameId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      frameId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Inertia decay
      if (!isDragging) {
        velocity.x *= 0.95;
        velocity.y *= 0.95;
        nodesGroup.rotation.y += velocity.x + 0.002;
        nodesGroup.rotation.x += velocity.y;
      }

      // Check Hover Raycasting
      raycaster.setFromCamera(mouse2D, camera);
      const meshes = pointMeshes.map((p) => p.mesh);
      const intersects = raycaster.intersectObjects(meshes, false);

      if (intersects.length > 0) {
        const found = pointMeshes.find((p) => p.mesh === intersects[0].object);
        if (found) {
          setHoveredPoint(found.data);
          container.style.cursor = "pointer";
        }
      } else {
        setHoveredPoint(null);
        container.style.cursor = isDragging ? "grabbing" : "grab";
      }

      // Update Dynamic Similarity Lines based on live slider threshold
      const thresh = thresholdRef.current;
      let lineCount = 0;
      const posArr = lineGeo.attributes.position.array as Float32Array;
      const colArr = lineGeo.attributes.color.array as Float32Array;

      for (let i = 0; i < SAMPLE_VECTORS.length; i++) {
        for (let j = i + 1; j < SAMPLE_VECTORS.length; j++) {
          const vA = SAMPLE_VECTORS[i];
          const vB = SAMPLE_VECTORS[j];

          // Compute pseudo-cosine similarity metric between clusters
          const isSameCluster = vA.cluster === vB.cluster;
          const sim = isSameCluster ? (vA.similarity + vB.similarity) / 2 : 0.45;

          if (sim >= thresh && lineCount < maxLines) {
            const li = lineCount * 6;
            posArr[li] = vA.pos[0];
            posArr[li + 1] = vA.pos[1];
            posArr[li + 2] = vA.pos[2];

            posArr[li + 3] = vB.pos[0];
            posArr[li + 4] = vB.pos[1];
            posArr[li + 5] = vB.pos[2];

            const col = CLUSTER_COLORS[vA.cluster]?.hex || 0x6366f1;
            const cObj = new THREE.Color(col);
            colArr[li] = cObj.r;
            colArr[li + 1] = cObj.g;
            colArr[li + 2] = cObj.b;

            colArr[li + 3] = cObj.r;
            colArr[li + 4] = cObj.g;
            colArr[li + 5] = cObj.b;

            lineCount++;
          }
        }
      }
      lineGeo.setDrawRange(0, lineCount * 2);
      lineGeo.attributes.position.needsUpdate = true;
      lineGeo.attributes.color.needsUpdate = true;

      // Pulse Halos & Highlight Selected Node
      pointMeshes.forEach((p) => {
        const isSelected = selectedPoint?.id === p.data.id;
        const isHovered = hoveredPoint?.id === p.data.id;
        const isSearchMatch = searchFilter.trim() !== "" && p.data.prompt.toLowerCase().includes(searchFilter.toLowerCase());

        p.halo.rotation.y += 0.02;
        p.halo.rotation.z += 0.015;

        const targetScale = isSelected ? 2.0 : isHovered || isSearchMatch ? 1.5 : 1.0;
        p.mesh.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.15);
      });

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(frameId);
      container.removeEventListener("mousedown", handlePointerDown);
      window.removeEventListener("mousemove", handlePointerMove);
      window.removeEventListener("mouseup", handlePointerUp);
      container.removeEventListener("click", handleClick);
      window.removeEventListener("resize", handleResize);

      if (container && renderer.domElement) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
      cageGeo.dispose();
      cageMat.dispose();
      lineGeo.dispose();
      lineMat.dispose();
    };
  }, [selectedPoint, hoveredPoint, searchFilter]);

  return (
    <div className={`relative border border-slate-800 bg-slate-950/80 overflow-hidden shadow-2xl ${className}`}>
      {/* 3D Top Header Bar */}
      <div className="absolute top-0 left-0 right-0 z-20 px-5 py-3.5 bg-[#07090e]/90 backdrop-blur-xl border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 bg-indigo-950/80 border border-indigo-500/50 flex items-center justify-center text-indigo-400">
            <Database className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-slate-100 uppercase tracking-tight">
                FastEmbed BGE-Small (384D) Semantic Topology
              </span>
              <span className="text-[9px] font-mono px-1.5 py-0.2 bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold">
                L2 VECTOR CACHE
              </span>
            </div>
            <p className="text-[10px] font-mono text-slate-500">
              Cosine similarity proximity matrix mapped via 3-axis PCA projection
            </p>
          </div>
        </div>

        {/* Live Controls: Similarity Slider & Search */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-900/80 border border-slate-800 px-3 py-1.5 text-xs font-mono">
            <Sliders className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-[10px] text-slate-400">COSINE THRESHOLD:</span>
            <input
              type="range"
              min="0.70"
              max="0.99"
              step="0.01"
              value={similarityThreshold}
              onChange={(e) => setSimilarityThreshold(parseFloat(e.target.value))}
              className="w-20 accent-indigo-500 cursor-pointer"
            />
            <span className="text-[11px] font-bold text-cyan-300 w-10 text-right">
              {(similarityThreshold * 100).toFixed(0)}%
            </span>
          </div>

          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search prompt vectors..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="bg-slate-900/80 border border-slate-800 pl-8 pr-3 py-1.5 text-xs font-mono text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-indigo-500 w-44"
            />
          </div>
        </div>
      </div>

      {/* Three.js Canvas Container */}
      <div ref={containerRef} className="w-full h-[520px] select-none" />

      {/* Floating Detailed Node Inspector Panel */}
      {selectedPoint && (
        <div className="absolute bottom-5 left-5 right-5 sm:right-auto sm:max-w-lg z-20 bg-[#07090e]/95 backdrop-blur-2xl border border-slate-700/80 p-5 shadow-2xl space-y-3 animate-in fade-in slide-in-from-bottom duration-200">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${CLUSTER_COLORS[selectedPoint.cluster]?.bg}`} />
              <span className={`text-xs font-mono font-bold uppercase tracking-wider ${CLUSTER_COLORS[selectedPoint.cluster]?.tailwind}`}>
                {selectedPoint.cluster}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono bg-emerald-950 text-emerald-300 border border-emerald-800 px-2 py-0.5 font-bold">
                COSINE MATCH: {(selectedPoint.similarity * 100).toFixed(1)}%
              </span>
              <span className="text-[10px] font-mono bg-indigo-950 text-indigo-300 border border-indigo-800 px-2 py-0.5">
                SAVED {selectedPoint.tokensSaved} TOKENS
              </span>
            </div>
          </div>

          <div>
            <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest block mb-1">PROMPT PAYLOAD</span>
            <p className="text-xs font-mono text-slate-200 bg-slate-950 p-2.5 border border-slate-800 leading-relaxed font-medium">
              &ldquo;{selectedPoint.prompt}&rdquo;
            </p>
          </div>

          <div className="grid grid-cols-3 gap-2 text-[10px] font-mono text-slate-400 pt-1">
            <div className="bg-slate-900/60 p-2 border border-slate-800">
              <span className="text-slate-500 block">MODEL:</span>
              <span className="text-slate-200 font-semibold">{selectedPoint.model}</span>
            </div>
            <div className="bg-slate-900/60 p-2 border border-slate-800">
              <span className="text-slate-500 block">TTL TIME:</span>
              <span className="text-emerald-400 font-semibold">{selectedPoint.ttl}s</span>
            </div>
            <div className="bg-slate-900/60 p-2 border border-slate-800">
              <span className="text-slate-500 block">FINGERPRINT:</span>
              <span className="text-indigo-300 font-semibold truncate block">{selectedPoint.hash}</span>
            </div>
          </div>
        </div>
      )}

      {/* Cluster Legend in Top-Right */}
      <div className="absolute top-16 right-5 z-10 hidden md:flex flex-col gap-1.5 bg-slate-950/80 backdrop-blur-md p-3 border border-slate-800 text-[10px] font-mono">
        <span className="text-slate-500 font-bold uppercase tracking-widest mb-1">SEMANTIC DOMAINS</span>
        {Object.entries(CLUSTER_COLORS).map(([name, conf]) => (
          <div key={name} className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: `#${conf.hex.toString(16).padStart(6, "0")}` }} />
            <span className="text-slate-300">{name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
