document.addEventListener("DOMContentLoaded", () => {
  const capabilitiesList = document.getElementById("capabilities-list");
  const capabilitySelect = document.getElementById("capability");
  const registerForm = document.getElementById("register-form");
  const messageDiv = document.getElementById("message");
  const approvalsContainer = document.getElementById("approvals-container");
  const approvalsList = document.getElementById("approvals-list");
  const authButton = document.getElementById("auth-button");
  const currentUser = document.getElementById("current-user");
  const loginModal = document.getElementById("login-modal");
  const closeModal = document.getElementById("close-modal");
  const loginForm = document.getElementById("login-form");

  let authToken = localStorage.getItem("sessionToken");
  let user = null;

  async function apiFetch(url, options = {}) {
    const headers = {
      ...(options.headers || {}),
    };

    if (authToken) {
      headers["X-Session-Token"] = authToken;
    }

    return fetch(url, {
      ...options,
      headers,
    });
  }

  function isPracticeLead() {
    return user && user.role === "practice_lead";
  }

  function showMessage(text, type = "success") {
    messageDiv.textContent = text;
    messageDiv.className = type;
    messageDiv.classList.remove("hidden");

    setTimeout(() => {
      messageDiv.classList.add("hidden");
    }, 5000);
  }

  function renderAuthState() {
    if (isPracticeLead()) {
      authButton.textContent = "Logout";
      currentUser.textContent = `Practice Lead: ${user.username}`;
      approvalsContainer.classList.remove("hidden");
    } else {
      authButton.textContent = "Practice Lead Login";
      currentUser.textContent = "Consultant View";
      approvalsContainer.classList.add("hidden");
    }
  }

  async function fetchCurrentUser() {
    if (!authToken) {
      user = null;
      renderAuthState();
      return;
    }

    try {
      const response = await apiFetch("/auth/me");
      if (!response.ok) {
        throw new Error("Session invalid");
      }

      user = await response.json();
    } catch (error) {
      authToken = null;
      user = null;
      localStorage.removeItem("sessionToken");
    }

    renderAuthState();
  }

  async function fetchPendingRequests() {
    if (!isPracticeLead()) {
      approvalsList.innerHTML = "<p>No pending requests.</p>";
      return;
    }

    try {
      const response = await apiFetch("/registration-requests?status=pending");
      const requests = await response.json();

      if (!response.ok) {
        approvalsList.innerHTML = "<p>Unable to load requests.</p>";
        return;
      }

      if (!requests.length) {
        approvalsList.innerHTML = "<p>No pending requests.</p>";
        return;
      }

      approvalsList.innerHTML = requests
        .map(
          (request) => `
            <div class="request-card">
              <p><strong>${request.email}</strong> requested <strong>${request.capability}</strong></p>
              <p class="helper-text">Requested at ${new Date(request.requested_at).toLocaleString()}</p>
              <div class="request-actions">
                <button class="approve-btn" data-id="${request.id}">Approve</button>
                <button class="reject-btn" data-id="${request.id}">Reject</button>
              </div>
            </div>
          `
        )
        .join("");

      document.querySelectorAll(".approve-btn").forEach((button) => {
        button.addEventListener("click", async (event) => {
          const requestId = event.target.getAttribute("data-id");
          const result = await apiFetch(`/registration-requests/${requestId}/approve`, {
            method: "POST",
          });
          const payload = await result.json();
          showMessage(payload.message || "Request approved", result.ok ? "success" : "error");
          if (result.ok) {
            fetchPendingRequests();
            fetchCapabilities();
          }
        });
      });

      document.querySelectorAll(".reject-btn").forEach((button) => {
        button.addEventListener("click", async (event) => {
          const requestId = event.target.getAttribute("data-id");
          const result = await apiFetch(`/registration-requests/${requestId}/reject`, {
            method: "POST",
          });
          const payload = await result.json();
          showMessage(payload.message || "Request rejected", result.ok ? "success" : "error");
          if (result.ok) {
            fetchPendingRequests();
          }
        });
      });
    } catch (error) {
      approvalsList.innerHTML = "<p>Unable to load requests.</p>";
    }
  }

  // Function to fetch capabilities from API
  async function fetchCapabilities() {
    try {
      const response = await apiFetch("/capabilities");
      const capabilities = await response.json();

      // Clear loading message
      capabilitiesList.innerHTML = "";
      capabilitySelect.innerHTML = '<option value="">-- Select a capability --</option>';

      // Populate capabilities list
      Object.entries(capabilities).forEach(([name, details]) => {
        const capabilityCard = document.createElement("div");
        capabilityCard.className = "capability-card";

        const availableCapacity = details.capacity || 0;
        const currentConsultants = details.consultants ? details.consultants.length : 0;

        // Create consultants HTML with delete icons
        const consultantsHTML =
          details.consultants && details.consultants.length > 0
            ? `<div class="consultants-section">
              <h5>Registered Consultants:</h5>
              <ul class="consultants-list">
                ${details.consultants
                  .map(
                    (email) =>
                      `<li><span class="consultant-email">${email}</span>${
                        isPracticeLead()
                          ? `<button class="delete-btn" data-capability="${name}" data-email="${email}">Remove</button>`
                          : ""
                      }</li>`
                  )
                  .join("")}
              </ul>
            </div>`
            : `<p><em>No consultants registered yet</em></p>`;

        capabilityCard.innerHTML = `
          <h4>${name}</h4>
          <p>${details.description}</p>
          <p><strong>Practice Area:</strong> ${details.practice_area}</p>
          <p><strong>Industry Verticals:</strong> ${details.industry_verticals ? details.industry_verticals.join(', ') : 'Not specified'}</p>
          <p><strong>Capacity:</strong> ${availableCapacity} hours/week available</p>
          <p><strong>Current Team:</strong> ${currentConsultants} consultants</p>
          <div class="consultants-container">
            ${consultantsHTML}
          </div>
        `;

        capabilitiesList.appendChild(capabilityCard);

        // Add option to select dropdown
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        capabilitySelect.appendChild(option);
      });

      // Add event listeners to delete buttons
      if (isPracticeLead()) {
        document.querySelectorAll(".delete-btn").forEach((button) => {
          button.addEventListener("click", handleUnregister);
        });
      }
    } catch (error) {
      capabilitiesList.innerHTML =
        "<p>Failed to load capabilities. Please try again later.</p>";
      console.error("Error fetching capabilities:", error);
    }
  }

  // Handle unregister functionality
  async function handleUnregister(event) {
    const button = event.target;
    const capability = button.getAttribute("data-capability");
    const email = button.getAttribute("data-email");

    try {
      const response = await fetch(
        `/capabilities/${encodeURIComponent(
          capability
        )}/unregister?email=${encodeURIComponent(email)}`,
        {
          method: "DELETE",
          headers: authToken
            ? {
                "X-Session-Token": authToken,
              }
            : {},
        }
      );

      const result = await response.json();

      if (response.ok) {
        showMessage(result.message, "success");

        // Refresh capabilities list to show updated consultants
        fetchCapabilities();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to unregister. Please try again.", "error");
      console.error("Error unregistering:", error);
    }
  }

  // Handle form submission
  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const email = document.getElementById("email").value;
    const capability = document.getElementById("capability").value;

    try {
      const response = await apiFetch(
        `/capabilities/${encodeURIComponent(
          capability
        )}/register?email=${encodeURIComponent(email)}`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (response.ok) {
        const messageType = result.status === "pending" ? "info" : "success";
        showMessage(result.message, messageType);
        registerForm.reset();

        // Refresh capabilities list to show updated consultants
        fetchCapabilities();
        fetchPendingRequests();
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to register. Please try again.", "error");
      console.error("Error registering:", error);
    }
  });

  authButton.addEventListener("click", async () => {
    if (isPracticeLead()) {
      await apiFetch("/auth/logout", { method: "POST" });
      authToken = null;
      user = null;
      localStorage.removeItem("sessionToken");
      renderAuthState();
      fetchCapabilities();
      fetchPendingRequests();
      return;
    }

    loginModal.classList.remove("hidden");
  });

  closeModal.addEventListener("click", () => {
    loginModal.classList.add("hidden");
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      const payload = await response.json();
      if (!response.ok) {
        showMessage(payload.detail || "Unable to sign in", "error");
        return;
      }

      authToken = payload.token;
      localStorage.setItem("sessionToken", authToken);
      user = payload.user;
      loginModal.classList.add("hidden");
      loginForm.reset();
      renderAuthState();
      showMessage(`Signed in as ${user.username}`, "success");
      fetchCapabilities();
      fetchPendingRequests();
    } catch (error) {
      showMessage("Unable to sign in. Please try again.", "error");
    }
  });

  // Initialize app
  fetchCurrentUser().then(() => {
    fetchCapabilities();
    fetchPendingRequests();
  });
});
