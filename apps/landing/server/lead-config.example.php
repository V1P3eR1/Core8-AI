<?php
/*
 * Copy to lead-config.php (same folder) and fill in. Never commit the real
 * file: it holds the shared secret. On shared hosting, also block direct web
 * access to it (the handler only ever `require`s it, so it prints nothing).
 */
return [
    // Mailbox that receives the leads.
    'to' => 'leads@example.invalid',
    // Sender address on YOUR domain; hosts usually reject mail() from foreign domains.
    'from' => 'Core8-AI website <no-reply@example.invalid>',
    // Long random string. The same value goes into the lead-triage tool as CORE8_LEAD_SECRET.
    'secret' => '',
    // Exact origins of the pages allowed to post the form.
    'allowed_origins' => ['https://www.example.invalid'],
    // Ids of consent wordings the owner approved. The page sends the id it showed.
    'consent_text_ids' => [],
    // Optional: write messages to this folder instead of sending (testing only).
    // 'spool_dir' => '/path/outside/webroot',
];
