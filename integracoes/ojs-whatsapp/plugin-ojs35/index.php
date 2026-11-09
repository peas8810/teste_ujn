<?php
declare(strict_types=1);

/**
 * OJS 3.5 generic plugin bootstrap.
 * Installed under: plugins/generic/ujnEditorialWa/
 */
require_once __DIR__ . '/EditorialWhatsAppRelay.php';
require_once __DIR__ . '/UjnEditorialWaPlugin.php';

return new \APP\plugins\generic\ujnEditorialWa\UjnEditorialWaPlugin();
