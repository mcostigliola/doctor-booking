const state = {
  bookings: [],
  selectedId: null,
};

const listEl = document.querySelector("[data-booking-list]");
const detailsEl = document.querySelector("[data-booking-details]");
const statusEl = document.querySelector("[data-booking-status]");
const messageEl = document.querySelector("[data-admin-message]");
const totalCountEl = document.querySelector("[data-total-count]");
const lastUpdateEl = document.querySelector("[data-last-update]");
const refreshBtn = document.querySelector("[data-refresh]");
const searchInput = document.querySelector("[data-search]");
const manualForm = document.querySelector("[data-manual-form]");
const manualDate = document.querySelector("[data-manual-date]");
const manualTime = document.querySelector("[data-manual-time]");

let availabilityCache = null;

const initReveal = () => {
  const revealItems = document.querySelectorAll(".reveal");
  if (!revealItems.length) return;

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
    item.style.transitionDelay = `${index * 100}ms`;
    observer.observe(item);
  });
};

const formatTime = (isoString) => {
  if (!isoString) return "--";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString("it-IT", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const setMessage = (text, tone = "info") => {
  if (!messageEl) return;
  const tones = {
    info: "text-slate-600 bg-sand",
    success: "text-moss bg-[#e6f1ee]",
    danger: "text-red-700 bg-[#fdeceb]",
  };
  messageEl.className = `mt-6 rounded-2xl px-4 py-3 text-sm ${tones[tone] || tones.info}`;
  messageEl.textContent = text;
};

const getFilteredBookings = () => {
  const query = (searchInput?.value || "").trim().toLowerCase();
  if (!query) return state.bookings;

  return state.bookings.filter((booking) => {
    const haystack = [
      booking.nome,
      booking.cognome,
      booking.telefono,
      booking.email,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
};

const renderList = () => {
  if (!listEl) return;
  listEl.innerHTML = "";

  const filteredBookings = getFilteredBookings();

  if (!filteredBookings.length) {
    listEl.innerHTML = `
      <div class="rounded-2xl border border-dashed border-slate-200 p-4 text-sm text-slate-500">
        Nessuna prenotazione trovata.
      </div>
    `;
    return;
  }

  filteredBookings.forEach((booking) => {
    const wrapper = document.createElement("button");
    wrapper.type = "button";
    wrapper.className = `w-full text-left rounded-2xl border px-4 py-3 transition slide-in ${
      state.selectedId === booking.id
        ? "border-ink bg-ink/5"
        : "border-slate-200 hover:-translate-y-0.5 hover:shadow-card"
    }`;

    const statusLabel = booking.status === "canceled" ? "Annullata" : "Prenotata";
    const attendedLabel = booking.attended ? "Presente" : "Assente";
    const paidLabel = booking.paid ? "Pagato" : "Non pagato";

    wrapper.innerHTML = `
      <div class="flex items-start justify-between gap-3">
        <div>
          <div class="text-base font-semibold">${booking.nome} ${booking.cognome}</div>
          <div class="mt-1 text-sm text-slate-600">${booking.data_ora || "Data non disponibile"}</div>
          <div class="mt-2 flex flex-wrap gap-2 text-xs">
            <span class="rounded-full bg-slate-100 px-2 py-1 text-slate-600">${statusLabel}</span>
            <span class="rounded-full bg-slate-100 px-2 py-1 text-slate-600">${attendedLabel}</span>
            <span class="rounded-full bg-slate-100 px-2 py-1 text-slate-600">${paidLabel}</span>
          </div>
        </div>
        <div class="text-xs text-slate-400">#${booking.id}</div>
      </div>
    `;

    wrapper.addEventListener("click", () => {
      state.selectedId = booking.id;
      renderList();
      renderDetails();
    });

    listEl.appendChild(wrapper);
  });
};

const renderDetails = () => {
  if (!detailsEl || !statusEl) return;
  const booking = state.bookings.find((item) => item.id === state.selectedId);

  if (!booking) {
    detailsEl.innerHTML = `
      <div class="rounded-2xl border border-dashed border-slate-200 p-4 text-sm text-slate-500">
        Seleziona una prenotazione per vedere i dettagli.
      </div>
    `;
    statusEl.textContent = "Nessuna selezione";
    return;
  }

  const statusLabel = booking.status === "canceled" ? "Annullata" : "Prenotata";
  statusEl.textContent = statusLabel;

  const cancelDisabled = booking.status === "canceled";
  detailsEl.innerHTML = `
    <div class="rounded-2xl bg-sand p-4">
      <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Anagrafica</p>
      <div class="mt-2 text-lg font-semibold">${booking.nome} ${booking.cognome}</div>
      <div class="mt-1 text-sm text-slate-600">${booking.email}</div>
      <div class="text-sm text-slate-600">${booking.telefono}</div>
    </div>
    <div class="grid gap-3 sm:grid-cols-2">
      <div class="rounded-2xl border border-slate-200 p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Visita</p>
        <div class="mt-2 text-sm font-semibold text-slate-700">${booking.data_ora || "Data non disponibile"}</div>
        <div class="mt-2 text-xs text-slate-500">Creata: ${formatTime(booking.created_at)}</div>
      </div>
      <div class="rounded-2xl border border-slate-200 p-4">
        <p class="text-xs uppercase tracking-[0.2em] text-slate-400">Note</p>
        <div class="mt-2 text-sm text-slate-700">${booking.note || "Nessuna nota"}</div>
      </div>
    </div>
    <div class="grid gap-3 sm:grid-cols-2">
      <button
        type="button"
        class="rounded-2xl border px-4 py-3 text-sm font-semibold transition ${
          booking.attended ? "border-moss bg-[#e6f1ee] text-moss" : "border-slate-200 hover:border-ink"
        }"
        data-action="attended"
      >
        ${booking.attended ? "Presenza confermata" : "Segna presenza"}
      </button>
    <button
      type="button"
      class="rounded-2xl border px-4 py-3 text-sm font-semibold transition ${
        booking.paid ? "border-moss bg-[#e6f1ee] text-moss" : "border-slate-200 hover:border-ink"
      }"
      data-action="paid"
    >
      ${booking.paid ? "Pagamento confermato" : "Segna pagamento"}
    </button>
  </div>
  <div class="grid gap-3 sm:grid-cols-2">
    <button
      type="button"
      class="rounded-2xl border px-4 py-3 text-sm font-semibold transition ${
        cancelDisabled
          ? "border-slate-200 bg-slate-100 text-slate-400"
          : "border-amber-200 text-amber-700 hover:border-amber-300 hover:bg-amber-50"
      }"
      data-action="cancel"
      ${cancelDisabled ? "disabled" : ""}
    >
      ${cancelDisabled ? "Prenotazione annullata" : "Annulla prenotazione"}
    </button>
    <button
      type="button"
      class="rounded-2xl border px-4 py-3 text-sm font-semibold transition border-red-200 text-red-700 hover:border-red-300 hover:bg-red-50"
      data-action="delete"
    >
      Elimina dal database
    </button>
  </div>
  <div class="rounded-2xl border border-slate-200 p-4 text-xs text-slate-500">
    Email ringraziamento: ${booking.thanked_at ? `inviata ${formatTime(booking.thanked_at)}` : "non inviata"}
  </div>
  `;

  detailsEl.querySelectorAll("button[data-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const action = btn.getAttribute("data-action");
      if (action === "attended") {
        await updateBooking(booking.id, { attended: !booking.attended });
      }
      if (action === "paid") {
        await updateBooking(booking.id, { paid: !booking.paid });
      }
      if (action === "cancel") {
        const confirmed = window.confirm("Vuoi annullare questa prenotazione?");
        if (!confirmed) {
          return;
        }
        await cancelBooking(booking.id);
      }
      if (action === "delete") {
        const confirmed = window.confirm("Vuoi eliminare definitivamente questa prenotazione?");
        if (!confirmed) {
          return;
        }
        await deleteBooking(booking.id);
      }
    });
  });
};

const cancelBooking = async (id) => {
  setMessage("Annullamento in corso...", "info");
  try {
    const response = await fetch("/api/bookings/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    if (!response.ok) {
      throw new Error("Annullamento non riuscito");
    }
    const data = await response.json();
    const updated = data.booking;
    state.bookings = state.bookings.map((item) => (item.id === updated.id ? updated : item));
    renderList();
    renderDetails();
    if (totalCountEl) {
      totalCountEl.textContent = getFilteredBookings().length;
    }
    await loadAvailability();
    setMessage("Prenotazione annullata.", "success");
  } catch (error) {
    setMessage("Errore durante l'annullamento. Riprova.", "danger");
  }
};

const deleteBooking = async (id) => {
  setMessage("Eliminazione in corso...", "info");
  try {
    const response = await fetch("/api/bookings/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id }),
    });
    if (!response.ok) {
      throw new Error("Eliminazione non riuscita");
    }
    state.bookings = state.bookings.filter((item) => item.id !== id);
    if (!state.bookings.length) {
      state.selectedId = null;
    } else if (state.selectedId === id) {
      state.selectedId = state.bookings[0].id;
    }
    renderList();
    renderDetails();
    if (totalCountEl) {
      totalCountEl.textContent = getFilteredBookings().length;
    }
    await loadAvailability();
    setMessage("Prenotazione eliminata.", "success");
  } catch (error) {
    setMessage("Errore durante l'eliminazione. Riprova.", "danger");
  }
};

const updateBooking = async (id, payload) => {
  setMessage("Aggiornamento in corso...", "info");
  try {
    const response = await fetch("/api/bookings/update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, ...payload }),
    });
    if (!response.ok) {
      throw new Error("Aggiornamento non riuscito");
    }
    const data = await response.json();
    const updated = data.booking;
    state.bookings = state.bookings.map((item) => (item.id === updated.id ? updated : item));
    renderList();
    renderDetails();
    if (totalCountEl) {
      totalCountEl.textContent = getFilteredBookings().length;
    }

    if (data.thank_you_email && data.thank_you_email.sent) {
      setMessage("Presenza confermata. Email di ringraziamento inviata.", "success");
    } else {
      setMessage("Prenotazione aggiornata.", "success");
    }
  } catch (error) {
    setMessage("Errore durante l'aggiornamento. Riprova.", "danger");
  }
};

const populateManualTimeOptions = (dateKey, availabilityResponse) => {
  if (!manualTime) return;
  manualTime.innerHTML = "";
  const dateItem = availabilityResponse.dates.find((item) => item.date === dateKey);
  const available = dateItem ? dateItem.available : [];

  availabilityResponse.timeSlots.forEach((slot) => {
    const option = document.createElement("option");
    option.value = slot;
    option.textContent = slot;
    if (!available.includes(slot)) {
      option.disabled = true;
      option.textContent += " · Non disponibile";
    }
    manualTime.appendChild(option);
  });

  const firstAvailable = Array.from(manualTime.options).find((opt) => !opt.disabled);
  if (firstAvailable) {
    firstAvailable.selected = true;
    manualTime.disabled = false;
  } else {
    manualTime.innerHTML = "<option>Nessuna disponibilita</option>";
    manualTime.disabled = true;
  }
};

const loadAvailability = async () => {
  if (!manualDate || !manualTime) return;
  try {
    const response = await fetch("/api/availability");
    if (!response.ok) {
      throw new Error("Errore disponibilita");
    }
    availabilityCache = await response.json();
    manualDate.min = availabilityCache.minDate;
    manualDate.max = availabilityCache.maxDate;
    manualDate.value = availabilityCache.minDate;
    populateManualTimeOptions(manualDate.value, availabilityCache);

    manualDate.addEventListener("change", (event) => {
      populateManualTimeOptions(event.target.value, availabilityCache);
    });
  } catch (error) {
    if (manualDate) {
      manualDate.value = "";
      manualDate.placeholder = "Server non disponibile";
      manualDate.disabled = true;
    }
    if (manualTime) {
      manualTime.innerHTML = "<option>Server non disponibile</option>";
      manualTime.disabled = true;
    }
  }
};

const createBooking = async (payload) => {
  setMessage("Salvataggio prenotazione...", "info");
  try {
    const response = await fetch("/api/bookings/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (response.status === 409) {
      setMessage("Slot gia occupato. Scegli un altro orario.", "danger");
      return;
    }
    if (!response.ok) {
      throw new Error("Creazione non riuscita");
    }
    const data = await response.json();
    const newBooking = data.booking;
    state.selectedId = newBooking.id;
    await loadBookings();
    await loadAvailability();
    if (manualForm) {
      manualForm.reset();
      if (availabilityCache && manualDate && manualTime) {
        manualDate.value = availabilityCache.minDate;
        populateManualTimeOptions(manualDate.value, availabilityCache);
      }
    }
    setMessage("Prenotazione inserita.", "success");
  } catch (error) {
    setMessage("Errore durante il salvataggio. Riprova.", "danger");
  }
};

const loadBookings = async () => {
  if (!listEl) return;
  listEl.innerHTML = `
    <div class="rounded-2xl border border-dashed border-slate-200 p-4 text-sm text-slate-500">
      Caricamento in corso...
    </div>
  `;
  try {
    const response = await fetch("/api/bookings");
    if (response.status === 401) {
      window.location.href = "/admin/login";
      return;
    }
    if (!response.ok) {
      throw new Error("Errore prenotazioni");
    }
    const data = await response.json();
    state.bookings = data.bookings || [];
    if (state.bookings.length && !state.selectedId) {
      state.selectedId = state.bookings[0].id;
    }
    renderList();
    renderDetails();
    if (totalCountEl) {
      totalCountEl.textContent = getFilteredBookings().length;
    }
    if (lastUpdateEl) {
      lastUpdateEl.textContent = `Ultimo aggiornamento: ${formatTime(new Date().toISOString())}`;
    }
    setMessage("Prenotazioni caricate.", "info");
  } catch (error) {
    listEl.innerHTML = `
      <div class="rounded-2xl border border-dashed border-red-200 bg-red-50 p-4 text-sm text-red-600">
        Impossibile caricare le prenotazioni. Verifica il server.
      </div>
    `;
    setMessage("Impossibile caricare le prenotazioni.", "danger");
  }
};

if (refreshBtn) {
  refreshBtn.addEventListener("click", () => {
    loadBookings();
  });
}

if (searchInput) {
  searchInput.addEventListener("input", () => {
    const filtered = getFilteredBookings();
    if (totalCountEl) {
      totalCountEl.textContent = filtered.length;
    }
    if (filtered.length && !filtered.some((item) => item.id === state.selectedId)) {
      state.selectedId = filtered[0].id;
    }
    renderList();
    renderDetails();
  });
}

initReveal();
loadBookings();
loadAvailability();

if (manualForm) {
  manualForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const formData = new FormData(manualForm);
    const payload = Object.fromEntries(formData.entries());
    createBooking(payload);
  });
}
