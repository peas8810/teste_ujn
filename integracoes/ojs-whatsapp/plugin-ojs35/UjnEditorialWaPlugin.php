<?php
declare(strict_types=1);

namespace APP\plugins\generic\ujnEditorialWa;

use PKP\plugins\GenericPlugin;
use PKP\plugins\Hook;
use UjnEditorialWhatsAppRelay;

/**
 * OJS 3.5.0.5 — event bridge. Does not send WhatsApp itself.
 * Event handlers intentionally never expose peer reviews or message bodies.
 * Requires environment configuration set by the journal hosting provider.
 */
final class UjnEditorialWaPlugin extends GenericPlugin
{
    public function register($category, $path, $mainContextId = null): bool
    {
        $registered = parent::register($category, $path, $mainContextId);
        if ($registered && $this->getEnabled($mainContextId)) {
            Hook::add('Submission::add', $this->onSubmissionAdded(...));
            Hook::add('Decision::add', $this->onDecisionAdded(...));
        }
        return $registered;
    }

    public function getDisplayName(): string
    {
        return 'Brain UJN — Alertas editoriais WhatsApp';
    }

    public function getDescription(): string
    {
        return 'Envia metadados de eventos editoriais à fila UJN. E-mails do OJS permanecem inalterados.';
    }

    private function transmit(int $submissionId, string $eventId, string $kind): void
    {
        if ($submissionId <= 0) {
            return;
        }
        $journal = getenv('UJN_OJS_WA_JOURNAL') ?: '';
        $secret = getenv('UJN_OJS_WA_SIGNING_KEY') ?: '';
        if (!in_array($journal, ['REMUNOM', 'JIRRS', 'NEXUS', 'RSV', 'RJNM'], true)
            || !preg_match('/^[0-9a-f]{64}$/i', $secret)) {
            error_log('UJN WA event skipped: missing journal configuration');
            return;
        }
        try {
            $ok = UjnEditorialWhatsAppRelay::deliver($journal, [
                'submission_id' => $submissionId,
                'event_id' => $eventId,
                'event_type' => $kind,
                'occurred_at' => gmdate('c'),
            ], $secret);
            if (!$ok) {
                error_log('UJN WA event enqueue failed; no OJS email or workflow changed');
            }
        } catch (\Throwable $error) {
            error_log('UJN WA event enqueue error; OJS workflow was not interrupted');
        }
    }

    public function onSubmissionAdded(string $hookName, array $params): bool
    {
        $submission = $params[0] ?? null;
        if (!is_object($submission) || !method_exists($submission, 'getId')) {
            return false;
        }
        $id = (int) $submission->getId();
        $this->transmit($id, 'submission.' . $id . '.created', 'submission_received');
        return false;
    }

    public function onDecisionAdded(string $hookName, array $params): bool
    {
        $decision = $params[0] ?? null;
        if (!is_object($decision) || !method_exists($decision, 'getId')
            || !method_exists($decision, 'getData')) {
            return false;
        }
        $id = (int) $decision->getId();
        $submissionId = (int) ($decision->getData('submissionId') ?: 0);
        if ($id > 0 && $submissionId > 0) {
            $this->transmit($submissionId, 'decision.' . $id . '.added', 'editorial_decision');
        }
        return false;
    }
}
