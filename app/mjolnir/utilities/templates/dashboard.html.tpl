<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mjolnir Vulnerability Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/github-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script type="text/javascript" src="https://www.gstatic.com/charts/loader.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script>
        (function() {
            let theme = 'dark';
            try {
                theme = localStorage.getItem('mjolnir-theme') || 'dark';
            } catch (e) {
                console.warn('localStorage not accessible, defaulting to dark theme', e);
            }
            document.documentElement.setAttribute('data-theme', theme);
        })();
    </script>
    <link rel="stylesheet" href="dashboard.css">
</head>
<body>
    <div class="app-layout">
{{sidebar}}
        <main class="main-content">
{{content}}
        </main>
    </div>

    <script>
        const pageData = {{page_data_json}};
    </script>
    <script src="dashboard.js" defer></script>
</body>
</html>
