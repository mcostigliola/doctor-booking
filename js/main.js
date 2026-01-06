window.tailwind = window.tailwind || {};
window.tailwind.config = {
  theme: {
    extend: {
      fontFamily: {
        sans: ["Space Grotesk", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Helvetica", "Arial"],
      },
      colors: {
        ink: "#0B0F1A",
      },
    },
  },
};

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", (event) => {
      const href = anchor.getAttribute("href");
      if (!href || href.length < 2) {
        return;
      }
      const target = document.querySelector(href);
      if (!target) {
        return;
      }
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  const revealItems = document.querySelectorAll(".reveal");
  if (revealItems.length) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("reveal--visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.18 }
    );

    revealItems.forEach((item, index) => {
      item.style.transitionDelay = `${index * 80}ms`;
      observer.observe(item);
    });
  }

  const dateSelect = document.querySelector("[data-booking-date]");
  const timeSelect = document.querySelector("[data-booking-time]");
  const availabilityMessage = document.querySelector("[data-availability-message]");

  if (!dateSelect || !timeSelect) {
    return;
  }

  const updateTimeOptions = (dateKey, availabilityResponse) => {
    timeSelect.innerHTML = "";
    const dateItem = availabilityResponse.dates.find((item) => item.date === dateKey);
    const available = dateItem ? dateItem.available : [];
    if (availabilityMessage) {
      availabilityMessage.textContent = available.length
        ? "Le prenotazioni sono disponibili fino a 2 mesi da oggi."
        : "Nessuna disponibilita per il giorno selezionato.";
    }
    availabilityResponse.timeSlots.forEach((slot) => {
      const option = document.createElement("option");
      option.value = slot;
      option.textContent = slot;
      if (!available.includes(slot)) {
        option.disabled = true;
        option.textContent += " · Non disponibile";
      }
      timeSelect.appendChild(option);
    });

    const firstAvailable = Array.from(timeSelect.options).find((opt) => !opt.disabled);
    if (firstAvailable) {
      firstAvailable.selected = true;
      timeSelect.disabled = false;
    } else {
      timeSelect.innerHTML = "<option>Nessuna disponibilita</option>";
      timeSelect.disabled = true;
    }
  };

  const loadAvailability = async () => {
    try {
      const response = await fetch("/api/availability");
      if (!response.ok) {
        throw new Error("Errore disponibilita");
      }
      const data = await response.json();
      dateSelect.min = data.minDate;
      dateSelect.max = data.maxDate;
      dateSelect.value = data.minDate;
      updateTimeOptions(dateSelect.value, data);

      dateSelect.addEventListener("change", (event) => {
        updateTimeOptions(event.target.value, data);
      });
    } catch (error) {
      dateSelect.value = "";
      dateSelect.placeholder = "Server non disponibile";
      timeSelect.innerHTML = "<option>Server non disponibile</option>";
      if (availabilityMessage) {
        availabilityMessage.textContent = "Server non disponibile.";
      }
      dateSelect.disabled = true;
      timeSelect.disabled = true;
    }
  };

  loadAvailability();
});
