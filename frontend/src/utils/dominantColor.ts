/** Извлекает доминантный цвет из изображения по URL.
 *  Загружает картинку в <img> → canvas → семплирует пиксели → возвращает hex.
 *  Результат кешируется, чтобы не пересчитывать каждый раз. */

const cache: Record<string, string> = {};

export const getDominantColor = async (url: string): Promise<string | null> => {
  if (cache[url]) return cache[url];

  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = url;

    img.onload = () => {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      if (!ctx) { resolve(null); return; }

      // Ресайз до 16×16 — достаточно для доминантного цвета
      canvas.width = 16;
      canvas.height = 16;
      ctx.drawImage(img, 0, 0, 16, 16);

      const data = ctx.getImageData(0, 0, 16, 16).data;
      const buckets: Record<number, { r: number; g: number; b: number; count: number }> = {};

      for (let i = 0; i < data.length; i += 4) {
        const r = data[i], g = data[i + 1], b = data[i + 2], a = data[i + 3];
        if (a < 128) continue;
        const brightness = (r * 299 + g * 587 + b * 114) / 1000;
        if (brightness > 240 || brightness < 20) continue;

        const key = ((r >> 5) << 10) | ((g >> 5) << 5) | (b >> 5); // 3-bit per channel
        if (!buckets[key]) buckets[key] = { r, g, b, count: 0 };
        buckets[key].count++;
      }

      let best = '';
      let bestCount = 0;
      for (const [k, v] of Object.entries(buckets)) {
        if (v.count > bestCount) { bestCount = v.count; best = k; }
      }

      if (!best) { resolve(null); return; }

      const { r, g, b } = buckets[best as unknown as number];
      const hex = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
      cache[url] = hex;
      resolve(hex);
    };

    img.onerror = () => resolve(null);
  });
};

/** Принять мапу (user_id → avatar_url) и вернуть мапу (user_id → hex_color) */
export const getDominantColorsMap = async (
  avatarMap: Record<string, string>
): Promise<Record<string, string>> => {
  const result: Record<string, string> = {};
  const entries = Object.entries(avatarMap);
  const colors = await Promise.all(entries.map(([uid, url]) => getDominantColor(url)));
  for (let i = 0; i < entries.length; i++) {
    if (colors[i]) result[entries[i][0]] = colors[i]!;
  }
  return result;
};