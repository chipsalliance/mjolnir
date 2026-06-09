<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vulnerability Scan Results Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <style>
{{dashboard_css}}
{{mjolnir_css}}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Vulnerability Scan Results Dashboard</h1>
            <p>Landing page for recent security analysis reports.</p>
        </header>

        <div class="grid">
{{cards_html}}
        </div>

        <footer>
            Generated automatically by aggregate_results.py
        </footer>
    </div>
</body>
</html>
