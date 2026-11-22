<?php
/*
 * Core8-AI landing page - lead form handler for PHP hosting (e.g. shared hosting).
 *
 * Receives the form as JSON, validates it, and e-mails one "CORE8 LEAD v1"
 * message to the business mailbox. It stores nothing except short-lived
 * rate-limit counters, and never logs names, addresses or messages.
 *
 * Nothing supplied by the visitor is ever placed in a mail header: the
 * subject is fixed and all visitor data travels inside a base64url block.
 *
 * Configuration lives in lead-config.php next to this file (copy
 * lead-config.example.php). Without it the handler answers 503.
 */
declare(strict_types=1);

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

function respond(int $status, array $body): never {
    http_response_code($status);
    echo json_encode($body);
    exit;
}
function clean(mixed $v, int $max): string {
    if (!is_string($v)) return '';
    $v = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]|\xE2\x80[\xAA-\xAE]|\xE2\x81[\xA6-\xA9]/u', ' ', $v) ?? '';
    return mb_substr(trim(str_replace(["\r\n", "\r"], "\n", $v)), 0, $max, 'UTF-8');
}
function b64url(string $s): string { return rtrim(strtr(base64_encode($s), '+/', '-_'), '='); }

$configFile = getenv('CORE8_LEAD_CONFIG') ?: __DIR__ . '/lead-config.php';
if (!is_file($configFile)) respond(503, ['ok' => false, 'error' => 'not_configured']);
$cfg = require $configFile;
foreach (['to', 'from', 'secret', 'allowed_origins', 'consent_text_ids'] as $key) {
    if (empty($cfg[$key])) respond(503, ['ok' => false, 'error' => 'not_configured']);
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') { header('Allow: POST'); respond(405, ['ok' => false, 'error' => 'method']); }
if (stripos($_SERVER['CONTENT_TYPE'] ?? '', 'application/json') !== 0) respond(415, ['ok' => false, 'error' => 'content_type']);

// Only the site's own pages may post here. This stops other websites using
// visitors' browsers; it is not a defence against scripts (see rate limit).
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin === '' || !in_array($origin, $cfg['allowed_origins'], true)) respond(403, ['ok' => false, 'error' => 'origin']);

$rawBody = file_get_contents('php://input', false, null, 0, 16385);
if ($rawBody === false || strlen($rawBody) > 16384) respond(413, ['ok' => false, 'error' => 'too_large']);
$in = json_decode($rawBody, true);
if (!is_array($in)) respond(400, ['ok' => false, 'error' => 'json']);

// Honeypot: answer exactly like a success and do nothing.
if (clean($in['website'] ?? '', 200) !== '') respond(202, ['ok' => true]);

// Rate limit: 5 submissions per address per 10 minutes. The address is stored
// only as a keyed hash, in the system temp folder.
$ipKey = hash_hmac('sha256', $_SERVER['REMOTE_ADDR'] ?? 'unknown', $cfg['secret']);
$rlDir = rtrim($cfg['rate_limit_dir'] ?? sys_get_temp_dir(), '/') . '/core8-lead-rl';
if (!is_dir($rlDir)) @mkdir($rlDir, 0700, true);
$rlFile = $rlDir . '/' . substr($ipKey, 0, 40);
$now = time();
$fh = @fopen($rlFile, 'c+');
if ($fh === false) respond(503, ['ok' => false, 'error' => 'unavailable']);
flock($fh, LOCK_EX);
$hits = array_values(array_filter(array_map('intval', explode("\n", (string) stream_get_contents($fh))), fn ($t) => $t > $now - 600));
if (count($hits) >= 5) { flock($fh, LOCK_UN); fclose($fh); header('Retry-After: 600'); respond(429, ['ok' => false, 'error' => 'rate_limited']); }
$hits[] = $now;
ftruncate($fh, 0); rewind($fh); fwrite($fh, implode("\n", $hits)); fflush($fh); flock($fh, LOCK_UN); fclose($fh);

$name = clean($in['name'] ?? '', 120);
$company = clean($in['company'] ?? '', 120);
$email = clean($in['email'] ?? '', 200);
$phone = clean($in['phone'] ?? '', 30);
$message = clean($in['message'] ?? '', 2000);
$lang = ($in['lang'] ?? '') === 'en' ? 'en' : 'he';
$consentId = clean($in['consent_text_id'] ?? '', 80);

if ($name === '') respond(422, ['ok' => false, 'error' => 'name']);
$emailOk = $email !== '' && filter_var($email, FILTER_VALIDATE_EMAIL) !== false;
$phoneOk = $phone !== '' && preg_match('/^\+?[\d\s().-]{7,20}$/', $phone) === 1 && preg_match_all('/\d/', $phone) >= 7;
if (($email !== '' && !$emailOk) || ($phone !== '' && !$phoneOk) || (!$emailOk && !$phoneOk)) respond(422, ['ok' => false, 'error' => 'contact']);
if (($in['consent'] ?? null) !== true) respond(422, ['ok' => false, 'error' => 'consent']);
// Consent must refer to a wording the owner approved and the page actually showed.
if (!in_array($consentId, $cfg['consent_text_ids'], true)) respond(409, ['ok' => false, 'error' => 'consent_text']);

$payload = json_encode([
    'v' => 1, 'id' => bin2hex(random_bytes(8)), 'submitted_at' => gmdate('Y-m-d\TH:i:s\Z', $now),
    'form' => 'landing', 'lang' => $lang, 'name' => $name, 'company' => $company, 'email' => $email,
    'phone' => $phone, 'message' => $message, 'consent' => true, 'consent_text_id' => $consentId,
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
$block = b64url($payload);
$body = implode("\n", [
    'New website inquiry (Core8-AI landing page).', 'Open the lead-triage tool to review it.', '',
    '-----BEGIN CORE8 LEAD v1-----', chunk_split($block, 60, "\n") . '-----END CORE8 LEAD v1-----',
    'sig: ' . hash_hmac('sha256', $block, $cfg['secret']), '',
]);
$subject = '[CORE8-LEAD] v1';
$headers = implode("\r\n", ['From: ' . $cfg['from'], 'MIME-Version: 1.0', 'Content-Type: text/plain; charset=UTF-8', 'Content-Transfer-Encoding: 7bit', 'X-Core8-Lead: v1']);

if (!empty($cfg['spool_dir'])) {
    // Test / dry-run mode: write the message to a folder instead of sending it.
    $sent = file_put_contents(rtrim($cfg['spool_dir'], '/') . '/lead-' . $now . '-' . bin2hex(random_bytes(4)) . '.txt', "To: {$cfg['to']}\nSubject: $subject\n$headers\n\n$body") !== false;
} else {
    $sent = mail($cfg['to'], $subject, $body, $headers);
}
if (!$sent) respond(502, ['ok' => false, 'error' => 'send_failed']);
respond(202, ['ok' => true]);
