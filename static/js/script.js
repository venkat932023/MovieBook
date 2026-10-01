
document.addEventListener("DOMContentLoaded", () => {
    const flashes = document.querySelectorAll(".flash");
    flashes.forEach((el) => setTimeout(() => {
        el.style.opacity = "0";
        el.style.transition = "opacity .4s";
        setTimeout(() => el.remove(), 450);
    }, 4500));
});
