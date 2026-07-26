import type { CompositionState, WorkbenchFragment } from "./compositionState";
import PromptComposerPanel from "./PromptComposerPanel";

interface PanelActions {
  onTextChange: (id: string, text: string) => void;
  onWeightChange: (id: string, weight: string) => void;
  onMove: (id: string, direction: -1 | 1) => void;
  onRemove: (id: string) => void;
  onFinalTextChange: (text: string) => void;
  onReapplySort: () => void;
}

interface Props {
  positive: CompositionState;
  negative: CompositionState;
  positiveActions: PanelActions;
  negativeActions: PanelActions;
  positiveArrangement: "auto" | "manual";
  negativeArrangement: "auto" | "manual";
  categoryInfoOf: (
    fragment: WorkbenchFragment,
  ) => { key: string; displayName: string; order: number } | null;
}

export default function PromptOverview({
  positive,
  negative,
  positiveActions,
  negativeActions,
  positiveArrangement,
  negativeArrangement,
  categoryInfoOf,
}: Props) {
  const { onReapplySort: onPositiveReapply, ...positiveRest } = positiveActions;
  const { onReapplySort: onNegativeReapply, ...negativeRest } = negativeActions;
  return (
    <div className="space-y-5">
      <PromptComposerPanel
        title="Positive Prompt"
        state={positive}
        arrangement={positiveArrangement}
        categoryInfoOf={categoryInfoOf}
        onReapplySort={onPositiveReapply}
        {...positiveRest}
      />
      <PromptComposerPanel
        title="Negative Prompt"
        state={negative}
        arrangement={negativeArrangement}
        categoryInfoOf={categoryInfoOf}
        onReapplySort={onNegativeReapply}
        {...negativeRest}
      />
    </div>
  );
}
