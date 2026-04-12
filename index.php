<?php
$ACCESS_KEY = "12345"; 

if (!isset($_GET['key']) || $_GET['key'] !== $ACCESS_KEY) {
    header('HTTP/1.1 403 Forbidden');
    die("Error: Access Denied");
}

$target_url = isset($_GET['url']) ? $_GET['url'] : '';
if (empty($target_url)) die("Usage: index.php?key=12345&url=LINK");

$scheme = (isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] === 'on') ? "https" : "http";
$proxy_self = $scheme . "://" . $_SERVER['HTTP_HOST'] . "/index.php?key=" . urlencode($ACCESS_KEY) . "&url=";

if (strpos($target_url, 'm3u8') !== false) {
    $ch = curl_init($target_url);
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
    curl_setopt($ch, CURLOPT_USERAGENT, 'Mozilla/5.0');
    $content = curl_exec($ch);
    curl_close($ch);

    $base_url = substr($target_url, 0, strrpos($target_url, '/') + 1);
    $lines = explode("\n", $content);
    $new_content = [];

    foreach ($lines as $line) {
        $line = trim($line);
        if (empty($line)) continue;
        if (strpos($line, '#') === 0) {
            $new_content[] = $line;
        } else {
            $full_url = (strpos($line, 'http') === 0) ? $line : $base_url . $line;
            $new_content[] = $proxy_self . urlencode($full_url);
        }
    }
    header('Content-Type: application/x-mpegURL');
    echo implode("\n", $new_content);
} else {
    header('Content-Type: video/mp2t');
    $ch = curl_init($target_url);
    curl_setopt($ch, CURLOPT_FOLLOWLOCATION, true);
    curl_setopt($ch, CURLOPT_USERAGENT, 'Mozilla/5.0');
    curl_exec($ch);
    curl_close($ch);
}
