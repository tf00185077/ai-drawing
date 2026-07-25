import type { CompositionState, RawCommitResult } from "./compositionState";
import PromptComposerPanel from "./PromptComposerPanel";

interface PanelActions {
  onTextChange: (id: string, text: string) => void;
  onWeightChange: (id: string, weight: string) => void;
  onMove: (id: string, direction: -1 | 1) => void;
  onRemove: (id: string) => void;
  onCommitRawText: (raw: string) => RawCommitResult;
  onRawDraftStateChange: (open: boolean) => void;
  rawResetVersion: number;
}

export default function PromptOverview({ positive, negative, positiveActions, negativeActions }: { positive: CompositionState; negative: CompositionState; positiveActions: PanelActions; negativeActions: PanelActions }) {
  return (
    <div className="space-y-5">
      <PromptComposerPanel title="Positive Prompt" state={positive} {...positiveActions} />
      <PromptComposerPanel title="Negative Prompt" state={negative} {...negativeActions} />
    </div>
  );
}
