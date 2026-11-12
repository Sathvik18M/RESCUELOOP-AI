"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { Globe } from "cobe";

/** Decorative only: no customer locations or application data are used. */
export function RotatingGlobe({ className = "" }: { className?: string }) {
  const rendererRef = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const id = useId().replace(/:/g, "");

  useEffect(() => {
    const host = rendererRef.current;
    if (!host) return;

    let disposed = false;
    let globe: Globe | undefined;
    let frame = 0;
    let previousTime = 0;
    let phi = 4.8;
    let inView = true;
    let initializedAt = 0;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const canvas = document.createElement("canvas");
    canvas.className = "rotating-globe-canvas";
    canvas.setAttribute("aria-hidden", "true");
    host.appendChild(canvas);

    function stop() {
      cancelAnimationFrame(frame);
      frame = 0;
      previousTime = 0;
    }

    function render(time: number) {
      frame = 0;
      if (disposed || !globe || document.hidden || !inView) return;
      // Time-based rotation stays consistent on both 60 Hz and 120 Hz screens.
      if (!motion.matches && previousTime) {
        phi += Math.min(time - previousTime, 50) * 0.00012;
      }
      previousTime = time;
      globe.update({ phi });
      // COBE loads its embedded map texture asynchronously. Give a static globe
      // time to render that texture too, without rotating for reduced motion.
      if (!motion.matches || time - initializedAt < 1500) {
        frame = requestAnimationFrame(render);
      }
    }

    function syncAnimation() {
      stop();
      if (globe && !document.hidden && inView) {
        frame = requestAnimationFrame(render);
      }
    }

    const resize = new ResizeObserver(() => {
      const size = Math.round(host!.getBoundingClientRect().width);
      if (size && globe) globe.update({ width: size, height: size });
    });
    const visibility = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      syncAnimation();
    });
    function contextLost() {
      stop();
      globe?.destroy();
      globe = undefined;
      if (!disposed) setReady(false);
    }

    canvas.addEventListener("webglcontextlost", contextLost);
    motion.addEventListener("change", syncAnimation);
    document.addEventListener("visibilitychange", syncAnimation);
    resize.observe(host);
    visibility.observe(host);

    async function initialize() {
      try {
        const { default: createGlobe } = await import("cobe");
        if (disposed) return;
        const context: WebGLContextAttributes = {
          alpha: true,
          antialias: true,
          depth: false,
          stencil: false,
          powerPreference: "low-power",
          preserveDrawingBuffer: false,
        };
        const gl =
          canvas.getContext("webgl2", context) ||
          canvas.getContext("webgl", context);
        if (!gl) return; // The server-rendered SVG remains visible.
        const size = Math.max(
          1,
          Math.round(host!.getBoundingClientRect().width),
        );
        globe = createGlobe(canvas, {
          // COBE 2 multiplies these CSS dimensions by devicePixelRatio itself.
          width: size,
          height: size,
          devicePixelRatio: Math.min(window.devicePixelRatio || 1, 1.5),
          phi,
          theta: 0.18,
          scale: 1.08,
          offset: [0, 0],
          dark: 0,
          diffuse: 1.2,
          mapSamples: size < 420 ? 12000 : 18000,
          mapBrightness: 6,
          baseColor: [1, 1, 1],
          markerColor: [1, 0.48, 0.08],
          glowColor: [1, 1, 1],
          markerElevation: 0,
          markers: [
            { location: [12.97, 77.59], size: 0.045 },
            { location: [1.35, 103.82], size: 0.025 },
            { location: [51.51, -0.13], size: 0.025 },
            { location: [25.2, 55.27], size: 0.025 },
            { location: [35.68, 139.69], size: 0.025 },
            { location: [40.71, -74.01], size: 0.025 },
          ],
          context,
        });
        initializedAt = performance.now();
        setReady(true);
        syncAnimation();
      } catch {
        // A decorative WebGL failure must never prevent the seller signing in.
        globe?.destroy();
        globe = undefined;
        if (!disposed) setReady(false);
      }
    }
    void initialize();

    return () => {
      disposed = true;
      stop();
      resize.disconnect();
      visibility.disconnect();
      motion.removeEventListener("change", syncAnimation);
      document.removeEventListener("visibilitychange", syncAnimation);
      canvas.removeEventListener("webglcontextlost", contextLost);
      globe?.destroy();
      // COBE owns this empty mount point, including the canvas wrapper it adds.
      host.replaceChildren();
    };
  }, []);

  return (
    <div
      className={`rotating-globe ${className}`.trim()}
      data-renderer={ready ? "webgl" : "static"}
      aria-hidden="true"
    >
      <svg
        className="rotating-globe-fallback"
        viewBox="0 0 600 600"
        focusable="false"
      >
        <defs>
          <radialGradient id={`${id}-sphere`} cx="40%" cy="30%" r="70%">
            <stop offset="0" stopColor="#fff" />
            <stop offset="0.65" stopColor="#f4f7f7" />
            <stop offset="0.9" stopColor="#cbd3d4" />
            <stop offset="1" stopColor="#fff" />
          </radialGradient>
          <pattern
            id={`${id}-dots`}
            width="6"
            height="6"
            patternUnits="userSpaceOnUse"
          >
            <circle cx="2" cy="2" r="1.5" fill="#778487" />
          </pattern>
          <clipPath id={`${id}-edge`}>
            <circle cx="300" cy="300" r="234" />
          </clipPath>
        </defs>
        <circle cx="300" cy="300" r="234" fill={`url(#${id}-sphere)`} />
        <g clipPath={`url(#${id}-edge)`} fill={`url(#${id}-dots)`}>
          <path d="M253 121l27-16 17 14 25-16 36 9 16-14 45 23 18-5 43 38 32 6 13 35-20 23-29-7-12 26-28-8-19 28-23-4-4 25-19 19-14-39-22-9-19-37-22-3-13-24-33-3-17-23-22-5z" />
          <path d="M230 211l36-19 45 14 26 34 7 30-28 27-11 39-21 38-23-9-9-41-19-23-26-48 9-20z" />
          <path d="M325 320l10 20-9 32-10 6-1-24zM387 279l20 9 7 22 28 9 8 18-26-3-22-16-13-13zM430 356l37-12 31 15 18 31-10 29-42 8-34-18-14-28zM470 446l15 7-4 25-14 7z" />
          <path d="M71 161l29-19 28 10 14 33-18 13 9 28 27 22-5 23-32-19-27-10-10-32-22-12zM137 272l29 7 26 31 1 32-19 25-8 38-16 20-15-34-4-40-18-29 5-29zM148 109l34-17 24 18-14 31-29 10z" />
        </g>
        <g fill="#ff901f" stroke="#ffd6a7" strokeWidth="2">
          <circle cx="362" cy="258" r="7" />
          <circle cx="398" cy="304" r="4" />
          <circle cx="266" cy="184" r="4" />
          <circle cx="468" cy="228" r="4" />
        </g>
      </svg>
      <div className="rotating-globe-renderer" ref={rendererRef} />
    </div>
  );
}
