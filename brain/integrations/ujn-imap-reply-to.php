<?php
/**
 * Brain UJN — extensão de cabeçalhos para o coletor IMAP existente.
 * Não acessa o banco, não envia e-mails. Extraia o Reply-To do MIME antes do POST sync_message.
 *
 * Integração, após obter $imap e $messageNumber:
 *   require_once __DIR__ . '/ujn-imap-reply-to.php';
 *   $meta = ujn_imap_reply_meta($imap, $messageNumber);
 *   $payload['reply_to'] = $meta['reply_to'];
 *   $payload['reply_to_name'] = $meta['reply_to_name'];
 */
declare(strict_types=1);

function ujn_imap_reply_meta($imap, int $messageNumber): array
{
    $headers = imap_headerinfo($imap, $messageNumber);
    if (!$headers) {
        return ['reply_to' => null, 'reply_to_name' => null];
    }
    // O Reply-To é o cabeçalho escolhido pelo remetente para o retorno.
    // Não extrair e-mails da assinatura ou de mensagens citadas.
    $candidates = $headers->reply_to ?? [];
    if (!is_array($candidates) || count($candidates) !== 1) {
        return ['reply_to' => null, 'reply_to_name' => null];
    }
    $entry = $candidates[0];
    if (!is_object($entry) || !isset($entry->mailbox, $entry->host)) {
        return ['reply_to' => null, 'reply_to_name' => null];
    }
    $address = strtolower(trim((string) $entry->mailbox . '@' . (string) $entry->host));
    if (!filter_var($address, FILTER_VALIDATE_EMAIL)
        || in_array($address, ['ujn@journals.ojsbr.com', 'contato@ujn.ojsbr.com'], true)) {
        return ['reply_to' => null, 'reply_to_name' => null];
    }
    $name = null;
    if (isset($entry->personal)) {
        $parts = imap_mime_header_decode((string) $entry->personal);
        $decoded = '';
        foreach ($parts as $part) {
            $text = (string) $part->text;
            if (strtolower((string) $part->charset) !== 'default' &&
                strtolower((string) $part->charset) !== 'utf-8' &&
                function_exists('mb_convert_encoding')) {
                $text = mb_convert_encoding($text, 'UTF-8', (string) $part->charset);
            }
            $decoded .= $text;
        }
        $name = substr(trim(preg_replace('/[\r\n<>]/', ' ', $decoded)), 0, 160) ?: null;
    }
    return ['reply_to' => $address, 'reply_to_name' => $name];
}
