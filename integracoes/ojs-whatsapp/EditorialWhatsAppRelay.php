<?php
/**
 * Brain UJN editorial event relay for OJS installations.
 *
 * This is a transport helper, NOT an installed OJS plugin. Integrate it with
 * the hooks supported by each journal's installed OJS/PKP version.
 *
 * Never put keys in publicly served PHP or JavaScript.
 */
declare(strict_types=1);

final class UjnEditorialWhatsAppRelay
{
    private const ENDPOINT =
        'https://leytqsyfrmzhectatcqm.supabase.co/functions/v1/ujn-editorial-ojs-events';

    private const JOURNALS = ['REMUNOM', 'JIRRS', 'NEXUS', 'RSV', 'RJNM'];

    /**
     * @param array<string,mixed> $event
     * Allowed keys: event_id, submission_id, event_type, occurred_at,
     * title, doi, public_url.
     */
    public static function deliver(string $journal, array $event, string $secret): bool
    {
        if (!in_array($journal, self::JOURNALS, true)) {
            throw new InvalidArgumentException('Unknown UJN journal');
        }
        if (!preg_match('/^[a-f0-9]{64}$/i', $secret)) {
            throw new InvalidArgumentException('Missing configured signing secret');
        }
        foreach (['event_id', 'submission_id', 'event_type'] as $required) {
            if (!array_key_exists($required, $event)) {
                throw new InvalidArgumentException('Missing editorial event field');
            }
        }
        // Deliberate allowlist: no reviews, reviewer details, messages,
        // file content, passwords or raw author contact data.
        $payload = [];
        foreach (['event_id', 'submission_id', 'event_type', 'occurred_at',
                  'title', 'doi', 'public_url'] as $field) {
            if (array_key_exists($field, $event)) {
                $payload[$field] = $event[$field];
            }
        }
        $body = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES
            | JSON_THROW_ON_ERROR);
        $timestamp = (string) time();
        $signature = 'sha256=' . hash_hmac('sha256', $timestamp . '.' . $body, $secret);
        $c = curl_init(self::ENDPOINT);
        curl_setopt_array($c, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => $body,
            CURLOPT_HTTPHEADER => [
                'Content-Type: application/json',
                'x-ujn-journal: ' . $journal,
                'x-ujn-timestamp: ' . $timestamp,
                'x-ujn-signature: ' . $signature,
            ],
            CURLOPT_CONNECTTIMEOUT => 5,
            CURLOPT_TIMEOUT => 10,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_FOLLOWLOCATION => false,
            CURLOPT_SSL_VERIFYPEER => true,
            CURLOPT_SSL_VERIFYHOST => 2,
        ]);
        $response = curl_exec($c);
        $status = (int) curl_getinfo($c, CURLINFO_HTTP_CODE);
        curl_close($c);
        return is_string($response) && $status === 200;
    }
}
