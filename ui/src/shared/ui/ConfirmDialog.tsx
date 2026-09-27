import { useId } from "react";

import { useT } from "@/shared/i18n";

import type { AskRequest } from "./ConfirmProvider";
import Modal from "./Modal";
import Sheen from "./Sheen";

// The gold answer is the app's one main action, drawn as Start and Save are: btn-start
const TONE_CLASS = {
  plain: "ui-modal-btn",
  primary: "ui-modal-btn btn-start",
  danger: "ui-modal-btn danger",
} as const;

interface ConfirmDialogProps {
  request: AskRequest;
  onAnswer: (choice: string | null) => void;
}

/**
 * Cancel is the cross in the corner, and it has the focus: Enter straight after the dialog
 * appears keeps the work. The answers follow in the order given, so the one the question leads
 * to sits last.
 */
export default function ConfirmDialog({ request, onAnswer }: ConfirmDialogProps) {
  const t = useT();
  const messageId = useId();

  return (
    <Modal
      role="alertdialog"
      labelledBy={messageId}
      closeLabel={t("common.dialog.cancel")}
      onClose={() => onAnswer(null)}
    >
      <p id={messageId} className="ui-modal-text">
        {request.message}
      </p>
      <div className="ui-modal-actions">
        {request.choices.map((choice) => (
          <button
            key={choice.id}
            type="button"
            className={TONE_CLASS[choice.tone ?? "plain"]}
            onClick={() => onAnswer(choice.id)}
          >
            {choice.tone === "primary" ? <Sheen tone="gold" /> : null}
            {choice.label}
          </button>
        ))}
      </div>
    </Modal>
  );
}
