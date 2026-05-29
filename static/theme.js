
// STEP 1: Apply theme IMMEDIATELY from localStorage (runs before DOM renders)
// This prevents any flash of wrong-colored page
(function() {
    // Check localStorage first (fastest - synchronous)
    let theme = localStorage.getItem('tavern-theme');
    
    // Default to dark if nothing in localStorage
    if (!theme) {
        theme = 'dark';
    }
    
    // Apply theme synchronously to html element
    applyThemeSync(theme);
})();

/**
 * Apply theme synchronously (no async operations)
 * Runs immediately when script loads, before DOM renders
 */
function applyThemeSync(theme) {
    const body = document.body;
    const isDark = theme === 'dark';
    
    // Remove both classes first
    body.classList.remove('light-theme');
    body.classList.remove('dark-theme');
    
    // Add the correct class
    body.classList.add(isDark ? 'dark-theme' : 'light-theme');
    
    // Store in localStorage for next page load
    localStorage.setItem('tavern-theme', theme);
}

/**
 * Apply theme fully (with page updates)
 */
function applyTheme(theme) {
    const html = document.documentElement;
    const body = document.body;
    const isDark = theme === 'dark';
    
    // Update HTML and body elements
    [html, body].forEach(el => {
        el.classList.remove('light-theme');
        el.classList.remove('dark-theme');
        el.classList.add(isDark ? 'dark-theme' : 'light-theme');
    });
    
    // Store preference
    localStorage.setItem('tavern-theme', theme);
}

/**
 * STEP 2: Sync with server config in background (non-blocking)
 * This validates that the theme matches server config
 * Runs after DOM is ready, so doesn't delay page rendering
 */
function syncThemeWithServer() {
    fetch('/api/theme')
        .then(response => response.json())
        .then(data => {
            const serverTheme = data.theme || 'dark';
            const currentTheme = localStorage.getItem('tavern-theme') || 'dark';
            
            // Only update if server config differs from current theme
            if (serverTheme !== currentTheme) {
                applyTheme(serverTheme);
                console.log('✓ Theme synced with server:', serverTheme);
            } else {
                console.log('✓ Theme matches server config:', serverTheme);
            }
        })
        .catch(error => {
            // Silently fail - already have a theme applied from localStorage
            console.debug('ℹ Could not sync theme with server (using localStorage)');
        });
}

// Run sync after document is ready (non-blocking)
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', syncThemeWithServer);
} else {
    // DOM already loaded, sync in next event loop
    setTimeout(syncThemeWithServer, 0);
}
