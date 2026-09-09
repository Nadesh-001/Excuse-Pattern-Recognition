document.addEventListener('DOMContentLoaded', () => {

    // --- MOBILE MENU TOGGLE ---
    const hamburger = document.querySelector('.hamburger');
    const mobileMenu = document.querySelector('.mobile-menu');

    if (hamburger && mobileMenu) {
        hamburger.addEventListener('click', () => {
            mobileMenu.classList.toggle('open');
            // Animate hamburger icon
            const spans = hamburger.querySelectorAll('span');
            if (mobileMenu.classList.contains('open')) {
                spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
                spans[1].style.opacity = '0';
                spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
            } else {
                spans[0].style.transform = 'none';
                spans[1].style.opacity = '1';
                spans[2].style.transform = 'none';
            }
        });

        // Close menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!hamburger.contains(e.target) && !mobileMenu.contains(e.target)) {
                mobileMenu.classList.remove('open');
                const spans = hamburger.querySelectorAll('span');
                spans[0].style.transform = 'none';
                spans[1].style.opacity = '1';
                spans[2].style.transform = 'none';
            }
        });
    }

    // --- CHART RENDERING (Simple CSS/JS Bar Charts) ---
    const bars = document.querySelectorAll('.bar');
    bars.forEach(bar => {
        const height = bar.style.height;
        bar.style.height = '0';
        setTimeout(() => {
            bar.style.height = height;
        }, 100);
    });

    // --- FEEDBACK INTERACTION ---
    const feedbackTags = document.querySelectorAll('.feedback-tag');
    feedbackTags.forEach(tag => {
        tag.addEventListener('click', function () {
            this.classList.toggle('active');
        });
    });

    const submitFeedbackBtn = document.getElementById('submit-feedback');
    if (submitFeedbackBtn) {
        submitFeedbackBtn.addEventListener('click', () => {
            const activeTags = Array.from(document.querySelectorAll('.feedback-tag.active')).map(t => t.innerText);
            const comment = document.querySelector('.feedback-area')?.value || '';
            console.log("Submitting Feedback:", { tags: activeTags, comment });
            submitFeedbackBtn.innerText = "Sent!";
            setTimeout(() => submitFeedbackBtn.innerText = "Submit Report", 2000);
        });
    }

    // --- CHATBOT ---
    const chatInput = document.getElementById('chatInput');
    const chatSend = document.getElementById('chatSend');
    const chatBody = document.getElementById('chatBody');

    function addMessage(text, isUser = false) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `msg ${isUser ? 'user' : 'ai'}`;
        const avatar = document.createElement('div');
        avatar.className = 'msg-avatar';
        avatar.innerText = isUser ? 'U' : 'AI';
        const content = document.createElement('div');
        content.className = 'msg-content';
        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble';
        bubble.innerText = text;
        const time = document.createElement('div');
        time.className = 'msg-time';
        time.innerText = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        content.appendChild(bubble);
        content.appendChild(time);
        msgDiv.appendChild(avatar);
        msgDiv.appendChild(content);
        chatBody?.appendChild(msgDiv);
        chatBody?.scrollTo(0, chatBody.scrollHeight);
    }

    async function handleChat() {
        const text = chatInput.value.trim();
        if (!text) return;

        // Add User Message
        addMessage(text, true);
        chatInput.value = '';

        // Show Typing Indicator
        const typingDiv = document.createElement('div');
        typingDiv.className = 'msg ai typing';
        typingDiv.id = 'typing-indicator';
        typingDiv.innerHTML = `<div class="msg-avatar">AI</div><div class="msg-bubble" style="padding: 12px;"><div class="typing-dots"><span></span><span></span><span></span></div></div>`;
        chatBody.appendChild(typingDiv);
        chatBody.scrollTo(0, chatBody.scrollHeight);

        try {
            const response = await fetch('/chatbot/api', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]')?.value || ''
                },
                body: JSON.stringify({ message: text })
            });

            // Remove Typing Indicator
            chatBody.removeChild(typingDiv);

            if (response.ok) {
                const data = await response.json();
                // Check if response is JSON with 'response' key or just text
                const aiText = data.response || "No response received.";
                addMessage(aiText, false); // Add AI Message

                // Render AI Analysis Card removed per user request

            } else {
                const errData = await response.json();
                addMessage(`⚠️ Error: ${errData.error || 'Failed to connect to AI.'}`, false);
            }

        } catch (error) {
            console.error("Chatbot Error:", error);
            if (document.getElementById('typing-indicator')) chatBody.removeChild(document.getElementById('typing-indicator'));
            addMessage("⚠️ Network Error: Could not reach AI service.", false);
        }
    }

    if (chatSend) {
        chatSend.addEventListener('click', handleChat);
        chatInput?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleChat();
        });
    }

});
