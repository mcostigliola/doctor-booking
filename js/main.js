window.tailwind = window.tailwind || {};
window.tailwind.config = {
  theme: {
    extend: {
      fontFamily: {
        sans: ["Manrope", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "Helvetica", "Arial"],
      },
      colors: {
        ink: "#0B0F1A",
      },
    },
  },
};

document.addEventListener("DOMContentLoaded", () => {
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
