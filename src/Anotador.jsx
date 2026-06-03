import React, { useEffect, useState, useRef } from "react";
import { FaTimes, FaSave, FaUndo } from "react-icons/fa";
import { FiLock } from "react-icons/fi";

export default function Anotador({
  image,
  initialData,
  onSave,
  onCancel,
  locked   = false,   // true → read-only, save button disabled
  editCount = 0,      // how many times this image has been saved already
  maxEdits  = 2,      // MAX_EDITS from App.jsx
}) {
  const [isDangerous, setIsDangerous] = useState(initialData?.isDangerous ?? false);
  const [notes,       setNotes]       = useState(initialData?.notes       ?? "");
  const [strokes,     setStrokes]     = useState(initialData?.strokes     ?? []);
  const [isDrawing,   setIsDrawing]   = useState(false);
  const canvasRef = useRef(null);
  const imageRef  = useRef(null);

  // Reset all state when the image changes (key prop in App.jsx also does this,
  // but keeping the effect as a safety net)
  useEffect(() => {
    setIsDangerous(initialData?.isDangerous ?? false);
    setNotes(initialData?.notes             ?? "");
    setStrokes(initialData?.strokes         ?? []);
    setIsDrawing(false);
  }, [image]);

  // Escape cancels
  useEffect(() => {
    const h = e => { if (e.key === "Escape") { setIsDrawing(false); onCancel(); } };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onCancel]);

  // Redraw canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    const imgEl  = imageRef.current;
    if (!canvas || !imgEl) return;
    const rect   = imgEl.getBoundingClientRect();
    canvas.width  = rect.width;
    canvas.height = rect.height;
    const ctx    = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    strokes.forEach(stroke => {
      if (!stroke.points.length) return;
      ctx.beginPath();
      stroke.points.forEach(([nx, ny], i) => {
        const x = nx * rect.width;
        const y = ny * rect.height;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.closePath();
      ctx.fillStyle   = locked ? "rgba(100,100,100,0.35)" : "rgba(0,0,255,0.5)";
      ctx.fill();
      ctx.strokeStyle = locked ? "#888" : "blue";
      ctx.lineWidth   = 5;
      ctx.lineCap     = "round";
      ctx.lineJoin    = "round";
      ctx.stroke();
    });
  }, [strokes, locked]);

  const roundTo = (n, d) => Math.round(n * 10 ** d) / 10 ** d;

  // Attach mousemove + mouseup to WINDOW so drawing continues and ends
  // correctly even when the cursor leaves the image boundary.
  // This fixes the "stroke gets cut off at the edge" bug.
  useEffect(() => {
    if (locked) return;

    const onMove = e => {
      if (!isDrawing) return;
      const r = imageRef.current.getBoundingClientRect();
      // Clamp to [0,1] so strokes that go outside the image edge stay on the border
      const xNorm = roundTo(Math.min(Math.max((e.clientX - r.left) / r.width,  0), 1), 5);
      const yNorm = roundTo(Math.min(Math.max((e.clientY - r.top)  / r.height, 0), 1), 5);
      setStrokes(prev => {
        const next = [...prev];
        next[next.length - 1].points.push([xNorm, yNorm]);
        return next;
      });
    };

    const onUp = () => setIsDrawing(false);

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup",   onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup",   onUp);
    };
  }, [isDrawing, locked]);

  const handleMouseDown = e => {
    if (locked) return;
    const r = imageRef.current.getBoundingClientRect();
    setIsDrawing(true);
    setStrokes(prev => [...prev, {
      id: Date.now(),
      points: [[(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height]],
    }]);
  };

  const handleUndo = () => { if (!locked) setStrokes(prev => prev.slice(0, -1)); };
  const handleSave       = () => { if (!locked) onSave({ isDangerous, notes, strokes }); };

  const editsLeft = maxEdits - editCount;

  return (
    <div style={{
      width: "100vw", height: "100vh",
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      background: locked ? "#f5f5f5" : "#fafafa",
      padding: 20, boxSizing: "border-box",
    }}>

      {/* Title + lock/edit status */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <h2 style={{ margin: 0 }}>
          {locked ? "Ver anotación" : editCount === 0 ? "Anotar imagen" : "Editar anotación"}
        </h2>
        {locked && (
          <span style={{
            display: "flex", alignItems: "center", gap: 5,
            background: "#e5e7eb", color: "#4b5563",
            fontSize: 12, padding: "3px 10px", borderRadius: 99,
          }}>
            <FiLock size={11} /> Bloqueada
          </span>
        )}
        {!locked && editCount > 0 && (
          <span style={{
            background: "#fef3c7", color: "#92400e",
            fontSize: 12, padding: "3px 10px", borderRadius: 99,
          }}>
            ⚠ {editsLeft === 1
              ? "Última edición disponible"
              : `${editsLeft} ediciones disponibles`}
          </span>
        )}
      </div>

      {/* Image + canvas */}
      <div
        ref={imageRef}
        style={{
          width: "80%", maxWidth: 900,
          borderRadius: 12, overflow: "hidden",
          boxShadow: "0 4px 20px rgba(0,0,0,0.12)",
          marginBottom: 18, position: "relative",
          opacity: locked ? 0.85 : 1,
        }}
      >
        <img src={image} alt="to-annotate"
          style={{ width: "100%", height: "60vh", objectFit: "cover", display: "block" }} />
        <canvas
          ref={canvasRef}
          style={{
            position: "absolute", top: 0, left: 0,
            width: "100%", height: "100%",
            cursor: locked ? "not-allowed" : "crosshair",
          }}
          onMouseDown={handleMouseDown}
        />
      </div>

      {/* Undo */}
      <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
        <button onClick={handleUndo}
          disabled={strokes.length === 0 || locked}
          style={{
            padding: "10px 14px", borderRadius: 8, border: "1px solid #ccc",
            background: (strokes.length === 0 || locked) ? "#f0f0f0" : "#fff",
            color:      (strokes.length === 0 || locked) ? "#999"    : "#000",
            cursor:     (strokes.length === 0 || locked) ? "not-allowed" : "pointer",
            display: "flex", alignItems: "center", gap: 8,
          }}
        >
          <FaUndo size={18} /> Deshacer
        </button>
      </div>

      {/* Toggle */}
      <label style={{ display: "flex", alignItems: "center", gap: 12,
                      marginBottom: 12, cursor: locked ? "not-allowed" : "pointer",
                      opacity: locked ? 0.6 : 1 }}>
        <span>¿Es peligrosa la escena?</span>
        <div
          onClick={() => { if (!locked) setIsDangerous(v => !v); }}
          style={{
            width: 52, height: 30, borderRadius: 999,
            background: isDangerous ? "#de8282ff" : "#d1d5db",
            position: "relative", padding: 4, boxSizing: "border-box",
            transition: "background 0.2s",
          }}
        >
          <div style={{
            width: 22, height: 22, borderRadius: "50%",
            background: "#fff", boxShadow: "0 2px 6px rgba(0,0,0,0.15)",
            position: "absolute", top: 4,
            left: isDangerous ? 26 : 4,
            transition: "left 0.18s",
          }} />
        </div>
      </label>

      {/* Notes */}
      <textarea
        placeholder={locked
          ? "(bloqueado — no editable)"
          : "Describe por qué es peligrosa, qué elementos ves, contexto..."}
        value={notes}
        readOnly={locked}
        onChange={e => { if (!locked) setNotes(e.target.value); }}
        style={{
          width: "80%", maxWidth: 800, height: 30,
          borderRadius: 8, padding: 12,
          border: "0.1px solid #ccc", fontSize: 15,
          resize: "vertical", marginBottom: 14,
          background: locked ? "#f3f4f6" : "#1a1a1aff",
          color: locked ? "#6b7280" : "#fff",
          cursor: locked ? "not-allowed" : "text",
        }}
      />

      {/* Buttons */}
      <div style={{ display: "flex", gap: 12 }}>
        <button onClick={onCancel} style={{
          padding: "10px 14px", borderRadius: 8,
          border: "1px solid #de8282ff", background: "#fff",
          color: "#de8282ff", cursor: "pointer",
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <FaTimes size={18} /> {locked ? "Cerrar" : "Cancelar"}
        </button>

        {!locked && (
          <button onClick={handleSave} style={{
            padding: "10px 14px", borderRadius: 8, border: "none",
            background: isDangerous ? "#de8282ff" : "#549664ff",
            color: "#fff", cursor: "pointer",
            display: "flex", alignItems: "center", gap: 8,
          }}>
            <FaSave size={18} />
            {editCount === 0 ? "Guardar" : "Guardar edición"}
          </button>
        )}
      </div>
    </div>
  );
}