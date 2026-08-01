// Esqueleto COCO-17 para entity_type=pose (PaddleX human_keypoint_detection).
// Formato tipico por joint: [x, y] o [x, y, score].

export type PoseJoint = { x: number; y: number; score: number };

export type PoseBone = {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
};

export type PoseJointDraw = PoseJoint & { color: string; index: number };

/** Pares 0-indexados del esqueleto COCO (nose…ankles). */
export const COCO_SKELETON: readonly [number, number][] = [
  [15, 13],
  [13, 11],
  [16, 14],
  [14, 12],
  [11, 12],
  [5, 11],
  [6, 12],
  [5, 6],
  [5, 7],
  [6, 8],
  [7, 9],
  [8, 10],
  [1, 2],
  [0, 1],
  [0, 2],
  [1, 3],
  [2, 4],
  [3, 5],
  [4, 6],
] as const;

/** Colores por zona corporal (L/R + cabeza/torso). */
const HEAD = "#f5d76e";
const TORSO = "#c4b5ff";
const LEFT_ARM = "#3ddc97";
const RIGHT_ARM = "#ff8a5c";
const LEFT_LEG = "#3f9bff";
const RIGHT_LEG = "#ff6b9d";

/** Color de joint COCO-17 por índice. */
export const COCO_JOINT_COLORS: readonly string[] = [
  HEAD, // 0 nose
  HEAD, // 1 left_eye
  HEAD, // 2 right_eye
  HEAD, // 3 left_ear
  HEAD, // 4 right_ear
  LEFT_ARM, // 5 left_shoulder
  RIGHT_ARM, // 6 right_shoulder
  LEFT_ARM, // 7 left_elbow
  RIGHT_ARM, // 8 right_elbow
  LEFT_ARM, // 9 left_wrist
  RIGHT_ARM, // 10 right_wrist
  LEFT_LEG, // 11 left_hip
  RIGHT_LEG, // 12 right_hip
  LEFT_LEG, // 13 left_knee
  RIGHT_LEG, // 14 right_knee
  LEFT_LEG, // 15 left_ankle
  RIGHT_LEG, // 16 right_ankle
];

function boneColor(a: number, b: number): string {
  // Prefer limb endpoints over torso when mixed.
  const limb = new Set([7, 8, 9, 10, 13, 14, 15, 16]);
  const pick = limb.has(a) ? a : limb.has(b) ? b : a;
  return COCO_JOINT_COLORS[pick] ?? TORSO;
}

const DEFAULT_MIN_SCORE = 0.2;

function asFiniteNumber(v: unknown): number | null {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** Normaliza un joint suelto ([x,y], [x,y,s], {x,y}, {x,y,score}). */
function parseOneJoint(raw: unknown): PoseJoint | null {
  if (Array.isArray(raw) && raw.length >= 2) {
    const x = asFiniteNumber(raw[0]);
    const y = asFiniteNumber(raw[1]);
    if (x === null || y === null) return null;
    const score = raw.length >= 3 ? (asFiniteNumber(raw[2]) ?? 1) : 1;
    return { x, y, score };
  }
  if (raw && typeof raw === "object") {
    const o = raw as Record<string, unknown>;
    const x = asFiniteNumber(o.x);
    const y = asFiniteNumber(o.y);
    if (x === null || y === null) return null;
    const score =
      asFiniteNumber(o.score) ?? asFiniteNumber(o.confidence) ?? asFiniteNumber(o.visibility) ?? 1;
    return { x, y, score };
  }
  return null;
}

/**
 * Acepta:
 * - [[x,y(,s)], …] (PaddleX keypoints / kpts)
 * - flat [x,y,s, x,y,s, …]
 * - { keypoints: […] } anidado
 */
export function parsePoseKeypoints(raw: unknown): PoseJoint[] {
  if (raw == null) return [];

  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const nested =
      (raw as { keypoints?: unknown }).keypoints ??
      (raw as { kpts?: unknown }).kpts ??
      (raw as { keypoint?: unknown }).keypoint;
    if (nested != null) return parsePoseKeypoints(nested);
    return [];
  }

  if (!Array.isArray(raw) || raw.length === 0) return [];

  // Lista de joints (objetos o [x,y(,s)]).
  if (typeof raw[0] === "object" || Array.isArray(raw[0])) {
    const joints: PoseJoint[] = [];
    for (const item of raw) {
      const j = parseOneJoint(item);
      if (j) joints.push(j);
    }
    return joints;
  }

  // Flat numérico: preferir triplets (x,y,s); si no divide exacto, pares (x,y).
  const nums = raw.map(asFiniteNumber);
  if (nums.every((n) => n !== null)) {
    const values = nums as number[];
    if (values.length % 3 === 0 && values.length >= 3) {
      const joints: PoseJoint[] = [];
      for (let i = 0; i < values.length; i += 3) {
        joints.push({ x: values[i], y: values[i + 1], score: values[i + 2] });
      }
      return joints;
    }
    if (values.length % 2 === 0) {
      const joints: PoseJoint[] = [];
      for (let i = 0; i < values.length; i += 2) {
        joints.push({ x: values[i], y: values[i + 1], score: 1 });
      }
      return joints;
    }
  }

  return [];
}

export function eventPoseKeypoints(payload: { keypoints?: unknown } | null | undefined): PoseJoint[] {
  if (!payload || !("keypoints" in payload)) return [];
  return parsePoseKeypoints(payload.keypoints);
}

export function visiblePoseBones(
  joints: PoseJoint[],
  minScore = DEFAULT_MIN_SCORE,
): PoseBone[] {
  const bones: PoseBone[] = [];
  for (const [a, b] of COCO_SKELETON) {
    const ja = joints[a];
    const jb = joints[b];
    if (!ja || !jb) continue;
    if (ja.score < minScore || jb.score < minScore) continue;
    bones.push({
      x1: ja.x,
      y1: ja.y,
      x2: jb.x,
      y2: jb.y,
      color: boneColor(a, b),
    });
  }
  return bones;
}

export function visiblePoseJoints(
  joints: PoseJoint[],
  minScore = DEFAULT_MIN_SCORE,
): PoseJointDraw[] {
  const out: PoseJointDraw[] = [];
  for (let i = 0; i < joints.length; i++) {
    const j = joints[i];
    if (j.score < minScore) continue;
    out.push({
      ...j,
      index: i,
      color: COCO_JOINT_COLORS[i] ?? TORSO,
    });
  }
  return out;
}
