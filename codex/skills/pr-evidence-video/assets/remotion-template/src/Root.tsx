import { Composition, type CalculateMetadataFunction } from "remotion";
import { EvidenceVideo, evidencePropsSchema, type EvidenceProps } from "./EvidenceVideo";

const DEFAULT_PROPS: EvidenceProps = {
  title: "PR evidence",
  primary: { src: "primary.mp4", label: "Primary" },
  labels: { primary: "Primary", secondary: "Comparison" },
  captions: [],
  zooms: [],
  comparison: { enabled: false, layout: "side-by-side" },
  durationInFrames: 150,
};

const calculateMetadata: CalculateMetadataFunction<EvidenceProps> = ({ props }) => ({
  durationInFrames: props.durationInFrames,
  fps: 30,
  width: 1280,
  height: 720,
});

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="PrEvidenceVideo"
      component={EvidenceVideo}
      durationInFrames={DEFAULT_PROPS.durationInFrames}
      fps={30}
      width={1280}
      height={720}
      defaultProps={DEFAULT_PROPS}
      schema={evidencePropsSchema}
      calculateMetadata={calculateMetadata}
    />
  );
};
