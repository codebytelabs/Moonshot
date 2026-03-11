'use client';

import { useState, useEffect } from 'react';

const CHARS = '01アイウエオカキクケコ10サシスセソタチツテト';

interface Column {
  left: string;
  delay: string;
  duration: string;
  char: string;
}

export default function DataRain() {
  const [columns, setColumns] = useState<Column[]>([]);

  useEffect(() => {
    // Generate random values only on client to avoid hydration mismatch
    setColumns(
      Array.from({ length: 30 }, (_, i) => ({
        left: `${(i / 30) * 100}%`,
        delay: `${Math.random() * 8}s`,
        duration: `${6 + Math.random() * 10}s`,
        char: CHARS[Math.floor(Math.random() * CHARS.length)],
      }))
    );
  }, []);

  if (columns.length === 0) return null;

  return (
    <div className="data-rain">
      {columns.map((col, i) => (
        <span
          key={i}
          style={{
            left: col.left,
            animationDelay: col.delay,
            animationDuration: col.duration,
          }}
        >
          {col.char}
        </span>
      ))}
    </div>
  );
}
