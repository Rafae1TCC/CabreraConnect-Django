        // Mobile navigation toggle
        document.addEventListener('DOMContentLoaded', function() {
            const navToggle = document.getElementById('navToggle');
            const navMenu = document.getElementById('navMenu');

            if (navToggle && navMenu) {
                navToggle.addEventListener('click', function() {
                    navToggle.classList.toggle('active');
                    navMenu.classList.toggle('active');
                });

                // Close menu when clicking on a link
                const navLinks = navMenu.querySelectorAll('.nav-link, .btn-logout');
                navLinks.forEach(link => {
                    link.addEventListener('click', () => {
                        navToggle.classList.remove('active');
                        navMenu.classList.remove('active');
                    });
                });

                // Close menu when clicking outside
                document.addEventListener('click', function(event) {
                    if (!navToggle.contains(event.target) && !navMenu.contains(event.target)) {
                        navToggle.classList.remove('active');
                        navMenu.classList.remove('active');
                    }
                });
            }
        });