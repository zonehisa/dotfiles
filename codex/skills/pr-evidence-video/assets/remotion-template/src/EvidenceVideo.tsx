import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { z } from "zod";

const localAsset = z
  .string()
  .min(1)
  .max(240)
  .refine((value) => !/^(?:https?|data):/i.test(value), "Only copied local assets are allowed")
  .refine((value) => !value.startsWith("/") && !value.includes("\\"), "Asset must be a relative public path")
  .refine((value) => !value.split("/").includes(".."), "Asset path must not escape public/");

const sourceSchema = z.object({
  src: localAsset,
  label: z.string().trim().min(1).max(80).optional(),
});

const captionSchema = z
  .object({
    text: z.string().trim().min(1).max(300),
    startMs: z.number().finite().nonnegative(),
    endMs: z.number().finite().positive(),
    timestampMs: z.number().finite().nonnegative().nullable().optional(),
    confidence: z.number().finite().min(0).max(1).nullable().optional(),
  })
  .refine((caption) => caption.endMs > caption.startMs, "Caption endMs must be after startMs")
  .refine((caption) => caption.endMs <= 60_000, "Caption must fit the bounded evidence duration");

const zoomSchema = z
  .object({
    startMs: z.number().finite().nonnegative(),
    endMs: z.number().finite().positive(),
    x: z.number().finite().min(0).max(1),
    y: z.number().finite().min(0).max(1),
    scale: z.number().finite().min(1).max(4),
  })
  .refine((zoom) => zoom.endMs > zoom.startMs, "Zoom endMs must be after startMs")
  .refine((zoom) => zoom.endMs <= 60_000, "Zoom must fit the bounded evidence duration");

const labelsSchema = z.object({
  primary: z.string().trim().min(1).max(80).optional(),
  secondary: z.string().trim().min(1).max(80).optional(),
});

const comparisonSchema = z.object({
  enabled: z.boolean(),
  layout: z.enum(["side-by-side", "stacked"]),
});

export const evidencePropsSchema = z.object({
  title: z.string().trim().min(1).max(200),
  primary: sourceSchema,
  secondary: sourceSchema.optional(),
  labels: labelsSchema,
  captions: z.array(captionSchema),
  zooms: z.array(zoomSchema),
  comparison: comparisonSchema,
  durationInFrames: z.number().int().min(30).max(1800),
});

export type EvidenceProps = z.infer<typeof evidencePropsSchema>;
type Source = EvidenceProps["primary"];
type Zoom = EvidenceProps["zooms"][number];

const WIDTH = 1280;
const HEIGHT = 720;
const SAFE_X = 80;
const SAFE_TOP = 100;
const SAFE_BOTTOM = 100;
const CONTENT_WIDTH = WIDTH - SAFE_X * 2;
const CONTENT_TOP = SAFE_TOP + 54;
const CONTENT_HEIGHT = HEIGHT - CONTENT_TOP - SAFE_BOTTOM;
const PANEL_GAP = 24;

const clamp = (value: number, min: number, max: number): number => Math.min(max, Math.max(min, value));

const activeZoom = (zooms: Zoom[], timeMs: number): Zoom | null => {
  const zoom = zooms.find((candidate) => timeMs >= candidate.startMs && timeMs <= candidate.endMs);
  return zoom ?? null;
};

const zoomStyle = (zooms: Zoom[], frame: number, fps: number): React.CSSProperties => {
  const timeMs = (frame / fps) * 1000;
  const zoom = activeZoom(zooms, timeMs);
  if (!zoom) {
    return { scale: 1 };
  }
  const transitionFrames = Math.max(1, Math.round(0.18 * fps));
  const startFrame = Math.round((zoom.startMs / 1000) * fps);
  const endFrame = Math.round((zoom.endMs / 1000) * fps);
  const scale = interpolate(
    frame,
    [startFrame, startFrame + transitionFrames, Math.max(startFrame + transitionFrames, endFrame - transitionFrames), endFrame],
    [1, clamp(zoom.scale, 1, 4), clamp(zoom.scale, 1, 4), 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  return {
    scale,
    transformOrigin: `${clamp(zoom.x, 0, 1) * 100}% ${clamp(zoom.y, 0, 1) * 100}%`,
  };
};

const VideoPanel: React.FC<{
  source: Source;
  label: string;
  zooms: Zoom[];
  frame: number;
  fps: number;
  width: number;
  height: number;
}> = ({ source, label, zooms, frame, fps, width, height }) => {
  return (
    <div
      style={{
        width,
        height,
        overflow: "hidden",
        position: "relative",
        borderRadius: 14,
        border: "2px solid #34415f",
        backgroundColor: "#030611",
      }}
    >
      <OffthreadVideo
        src={staticFile(source.src)}
        muted
        style={{
          width: "100%",
          height: "100%",
          objectFit: "contain",
          backgroundColor: "#030611",
          ...zoomStyle(zooms, frame, fps),
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 18,
          top: 16,
          padding: "8px 14px",
          borderRadius: 999,
          backgroundColor: "rgba(11, 16, 32, 0.88)",
          color: "#dce6ff",
          fontSize: 22,
          fontWeight: 700,
          letterSpacing: 0.4,
        }}
      >
        {label}
      </div>
    </div>
  );
};

export const EvidenceVideo: React.FC<EvidenceProps> = (props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentMs = (frame / fps) * 1000;
  const caption = props.captions.find((item) => currentMs >= item.startMs && currentMs <= item.endMs);
  const primaryLabel = props.labels.primary ?? props.primary.label ?? "Primary";
  const secondaryLabel = props.labels.secondary ?? props.secondary?.label ?? "Comparison";
  const isComparison = Boolean(props.secondary && props.comparison.enabled);
  const titleOpacity = interpolate(frame, [0, 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const panelHeight = isComparison && props.comparison.layout === "stacked" ? (CONTENT_HEIGHT - PANEL_GAP) / 2 : CONTENT_HEIGHT;
  const panelWidth = isComparison && props.comparison.layout === "side-by-side" ? (CONTENT_WIDTH - PANEL_GAP) / 2 : CONTENT_WIDTH;

  return (
    <AbsoluteFill style={{ backgroundColor: "#0b1020", color: "#f4f7ff", fontFamily: "Arial, sans-serif" }}>
      <div style={{ position: "absolute", left: SAFE_X, right: SAFE_X, top: SAFE_TOP, height: 48, opacity: titleOpacity }}>
        <div style={{ fontSize: 30, fontWeight: 800, lineHeight: 1.2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {props.title}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: SAFE_X,
          top: CONTENT_TOP,
          width: CONTENT_WIDTH,
          height: CONTENT_HEIGHT,
          display: "flex",
          flexDirection: props.comparison.layout === "stacked" ? "column" : "row",
          gap: PANEL_GAP,
        }}
      >
        <VideoPanel source={props.primary} label={primaryLabel} zooms={props.zooms} frame={frame} fps={fps} width={panelWidth} height={panelHeight} />
        {isComparison && props.secondary ? (
          <VideoPanel source={props.secondary} label={secondaryLabel} zooms={props.zooms} frame={frame} fps={fps} width={panelWidth} height={panelHeight} />
        ) : null}
      </div>
      {caption ? (
        <div
          style={{
            position: "absolute",
            left: SAFE_X + 24,
            right: SAFE_X + 24,
            bottom: SAFE_BOTTOM + 18,
            padding: "12px 22px",
            borderRadius: 12,
            backgroundColor: "rgba(3, 6, 17, 0.90)",
            color: "#ffffff",
            fontSize: 30,
            fontWeight: 700,
            lineHeight: 1.25,
            textAlign: "center",
            overflow: "hidden",
            maxHeight: 86,
          }}
        >
          {caption.text}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};
