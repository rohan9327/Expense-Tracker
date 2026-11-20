
// Automatically hide flash messages after 4 seconds

document.addEventListener("DOMContentLoaded", function () {

    const messages = document.querySelectorAll(".flash");

    messages.forEach(function (message) {

        setTimeout(function () {
            message.style.transition = "opacity 0.5s";
            message.style.opacity = "0";

            setTimeout(function () {
                message.remove();
            }, 500);

        }, 4000);

    });

});
