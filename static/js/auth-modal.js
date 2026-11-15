/**
 * LabFinder Global Auth Modal
 * Panels: login → signup email → OTP → complete profile
 * LinkedIn uses existing provider URLs on the modal.
 */
window.GlobalAuth = {
    isUserAuthenticated: false,
    onSuccessCallback: null,
    defaultGroup: 'Customer',
    pendingEmail: '',
    otpTimerInterval: null,
    otpSecondsLeft: 60,

    init: function () {
        var self = this;
        var authElement = document.getElementById('user-authenticated-data');
        if (authElement) {
            try {
                this.isUserAuthenticated = JSON.parse(authElement.textContent);
            } catch (e) {
                this.isUserAuthenticated = false;
            }
        }

        var authModal = document.getElementById('authPromptModal');
        var btnCloseModal = document.getElementById('btnCloseAuthModal');
        if (btnCloseModal) {
            btnCloseModal.addEventListener('click', function () { self.closeModal(); });
        }
        if (authModal) {
            authModal.addEventListener('click', function (e) {
                if (e.target === authModal) self.closeModal();
            });
        }

        var goSignup = document.getElementById('authGoSignup');
        var goLogin = document.getElementById('authGoLogin');
        if (goSignup) goSignup.addEventListener('click', function () { self.showPanel('signup'); });
        if (goLogin) goLogin.addEventListener('click', function () { self.showPanel('login'); });

        var otpBack = document.getElementById('authOtpBack');
        if (otpBack) otpBack.addEventListener('click', function () { self.showPanel('signup'); });

        this.bindGlobalTriggers();
        try {
            this.bindLoginForm();
            this.bindSignupEmailForm();
            this.bindOtpForm();
            this.bindProfileForm();
            this.bindOtpDigits();
            this.bindResendOtp();
        } catch (err) {
            console.warn('GlobalAuth form bind error:', err);
        }
    },

    bindGlobalTriggers: function () {
        var self = this;
        // Header / any [data-open-auth="login|signup"]
        document.addEventListener('click', function (e) {
            var t = e.target.closest('[data-open-auth], #enq-btn-signin, .js-open-auth-login, .js-open-auth-signup');
            if (!t) return;
            e.preventDefault();
            e.stopPropagation();
            var mode = t.getAttribute('data-open-auth');
            if (!mode) {
                if (t.classList.contains('js-open-auth-signup') || t.id === 'enq-btn-signup') mode = 'signup';
                else mode = 'login';
            }
            if (window.GlobalAuth && typeof window.GlobalAuth.openModal === 'function') {
                self.openModal(null, null, null, 'Customer', mode);
            }
        });
        var globalTrigger = document.getElementById('globalLoginTrigger');
        if (globalTrigger) {
            globalTrigger.addEventListener('click', function (e) {
                e.preventDefault();
                self.openModal();
            });
        }
    },

    showPanel: function (name) {
        var map = {
            login: 'authPanelLogin',
            signup: 'authPanelSignup',
            otp: 'authPanelOtp',
            profile: 'authPanelProfile'
        };
        Object.keys(map).forEach(function (key) {
            var el = document.getElementById(map[key]);
            if (el) el.classList.toggle('is-active', key === name);
        });
        this.hideAlert();
    },

    openModal: function (title, subtitle, onSuccess, groupName, panel) {
        if (typeof onSuccess === 'function') this.onSuccessCallback = onSuccess;
        if (groupName) this.defaultGroup = groupName;
        var groupInput = document.getElementById('profileUserGroup');
        if (groupInput) groupInput.value = this.defaultGroup;

        this.showPanel(panel || 'login');

        // Optional title override only on login panel defaults
        if (title) {
            var t = document.getElementById('modalAuthTitle');
            if (t) t.textContent = title;
        }
        if (subtitle) {
            var s = document.getElementById('modalAuthSubTitle');
            if (s) s.textContent = subtitle;
        }

        var authModal = document.getElementById('authPromptModal');
        if (authModal) {
            authModal.classList.add('is-open');
            authModal.style.setProperty('display', 'flex', 'important');
            document.body.classList.add('lf-auth-open');
        } else {
            console.warn('GlobalAuth: #authPromptModal not found in DOM');
        }
    },

    closeModal: function () {
        var authModal = document.getElementById('authPromptModal');
        if (authModal) {
            authModal.classList.remove('is-open');
            authModal.style.setProperty('display', 'none', 'important');
        }
        document.body.classList.remove('lf-auth-open');
        this.stopOtpTimer();
    },

    showAlert: function (msg, isSuccess) {
        var modalAlert = document.getElementById('modalAuthAlert');
        if (!modalAlert) return;
        modalAlert.style.display = 'block';
        modalAlert.className = 'lf-auth-alert ' + (isSuccess ? 'is-success' : 'is-error');
        modalAlert.textContent = msg;
    },

    hideAlert: function () {
        var modalAlert = document.getElementById('modalAuthAlert');
        if (modalAlert) {
            modalAlert.style.display = 'none';
            modalAlert.textContent = '';
        }
    },

    getCsrfToken: function () {
        var input = document.querySelector('#authPromptModal input[name="csrfmiddlewaretoken"]');
        if (input) return input.value;
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : '';
    },

    bindLoginForm: function () {
        var self = this;
        var form = document.getElementById('modalLoginForm');
        if (!form) return;
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var formData = new FormData(form);
            var actionUrl = form.getAttribute('data-action-url');
            fetch(actionUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': formData.get('csrfmiddlewaretoken') },
                body: formData
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.success) {
                        self.showAlert('Login successful!', true);
                        self.isUserAuthenticated = true;
                        setTimeout(function () {
                            self.closeModal();
                            if (typeof self.onSuccessCallback === 'function') {
                                self.onSuccessCallback();
                            } else {
                                window.location.reload();
                            }
                        }, 600);
                    } else {
                        self.showAlert(data.message || 'Invalid login credentials.', false);
                    }
                })
                .catch(function () {
                    self.showAlert('Authentication failed. Please try again.', false);
                });
        });
    },

    bindSignupEmailForm: function () {
        var self = this;
        var form = document.getElementById('modalSignupEmailForm');
        if (!form) return;
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var emailInput = document.getElementById('signupEmailInput');
            var email = (emailInput && emailInput.value || '').trim().toLowerCase();
            if (!email) {
                self.showAlert('Please enter a valid email address.', false);
                return;
            }
            var btn = document.getElementById('btnSendOtp');
            if (btn) { btn.disabled = true; btn.textContent = 'Sending…'; }
            var actionUrl = form.getAttribute('data-action-url');
            fetch(actionUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': self.getCsrfToken()
                },
                body: JSON.stringify({ email: email })
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (btn) { btn.disabled = false; btn.textContent = 'Send OTP'; }
                    if (data.success) {
                        self.pendingEmail = email;
                        var disp = document.getElementById('otpEmailDisplay');
                        var hid = document.getElementById('otpEmailHidden');
                        var pe = document.getElementById('profileEmailHidden');
                        if (disp) disp.textContent = email;
                        if (hid) hid.value = email;
                        if (pe) pe.value = email;
                        self.showPanel('otp');
                        self.startOtpTimer(60);
                        self.showAlert(data.message || 'OTP sent successfully.', true);
                    } else {
                        self.showAlert(data.message || 'Unable to send OTP.', false);
                    }
                })
                .catch(function () {
                    if (btn) { btn.disabled = false; btn.textContent = 'Send OTP'; }
                    self.showAlert('Unable to send OTP. Please try again.', false);
                });
        });
    },

    bindOtpDigits: function () {
        var digits = document.querySelectorAll('#otpDigitRow .lf-otp-digit');
        if (!digits.length) return;
        digits.forEach(function (digit, index) {
            digit.addEventListener('input', function () {
                digit.value = digit.value.replace(/\D/g, '').slice(0, 1);
                if (digit.value && index < digits.length - 1) digits[index + 1].focus();
            });
            digit.addEventListener('keydown', function (e) {
                if (e.key === 'Backspace' && !digit.value && index > 0) {
                    digits[index - 1].focus();
                }
            });
            digit.addEventListener('paste', function (e) {
                var text = (e.clipboardData || window.clipboardData).getData('text') || '';
                var nums = text.replace(/\D/g, '').slice(0, digits.length);
                if (!nums) return;
                e.preventDefault();
                for (var i = 0; i < digits.length; i++) {
                    digits[i].value = nums[i] || '';
                }
                digits[Math.min(nums.length, digits.length) - 1].focus();
            });
        });
    },

    getOtpValue: function () {
        var digits = document.querySelectorAll('#otpDigitRow .lf-otp-digit');
        var v = '';
        digits.forEach(function (d) { v += d.value || ''; });
        return v;
    },

    bindOtpForm: function () {
        var self = this;
        var form = document.getElementById('modalOtpForm');
        if (!form) return;
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var otp = self.getOtpValue();
            if (otp.length !== 5) {
                self.showAlert('Please enter the 5-digit verification code.', false);
                return;
            }
            var email = self.pendingEmail || (document.getElementById('otpEmailHidden') || {}).value || '';
            var actionUrl = form.getAttribute('data-action-url');
            var body = new FormData();
            body.append('email', email);
            body.append('otp', otp);
            body.append('csrfmiddlewaretoken', self.getCsrfToken());

            fetch(actionUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': self.getCsrfToken() },
                body: body
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.success) {
                        self.stopOtpTimer();
                        var pe = document.getElementById('profileEmailHidden');
                        if (pe) pe.value = email;
                        self.showPanel('profile');
                        self.showAlert('Email verified. Complete your profile.', true);
                    } else {
                        self.showAlert(data.message || 'Invalid verification code.', false);
                    }
                })
                .catch(function () {
                    self.showAlert('Verification failed. Please try again.', false);
                });
        });
    },

    startOtpTimer: function (seconds) {
        var self = this;
        this.stopOtpTimer();
        this.otpSecondsLeft = seconds || 60;
        var timerEl = document.getElementById('otpTimer');
        var resendBtn = document.getElementById('btnResendOtp');
        if (resendBtn) resendBtn.style.display = 'none';
        if (timerEl) timerEl.style.display = 'inline';

        function tick() {
            var m = Math.floor(self.otpSecondsLeft / 60);
            var s = self.otpSecondsLeft % 60;
            if (timerEl) {
                timerEl.textContent =
                    (m < 10 ? '0' : '') + m + ':' + (s < 10 ? '0' : '') + s;
            }
            if (self.otpSecondsLeft <= 0) {
                self.stopOtpTimer();
                if (timerEl) timerEl.style.display = 'none';
                if (resendBtn) resendBtn.style.display = 'inline';
                return;
            }
            self.otpSecondsLeft -= 1;
        }
        tick();
        this.otpTimerInterval = setInterval(tick, 1000);
    },

    stopOtpTimer: function () {
        if (this.otpTimerInterval) {
            clearInterval(this.otpTimerInterval);
            this.otpTimerInterval = null;
        }
    },

    bindResendOtp: function () {
        var self = this;
        var btn = document.getElementById('btnResendOtp');
        if (!btn) return;
        btn.addEventListener('click', function () {
            var email = self.pendingEmail;
            if (!email) return;
            var registerUrl = (document.getElementById('modalSignupEmailForm') || {}).getAttribute('data-action-url');
            fetch(registerUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': self.getCsrfToken()
                },
                body: JSON.stringify({ email: email })
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.success) {
                        self.startOtpTimer(60);
                        self.showAlert('A new code has been sent.', true);
                    } else {
                        self.showAlert(data.message || 'Could not resend OTP.', false);
                    }
                })
                .catch(function () {
                    self.showAlert('Could not resend OTP.', false);
                });
        });
    },

    bindProfileForm: function () {
        var self = this;
        var form = document.getElementById('modalProfileForm');
        if (!form) return;
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var formData = new FormData(form);
            var pass = formData.get('password') || '';
            var confirm = formData.get('password_confirm') || '';
            if (pass.length < 8) {
                self.showAlert('Password must be at least 8 characters.', false);
                return;
            }
            if (pass !== confirm) {
                self.showAlert('Passwords do not match.', false);
                return;
            }
            var first = (formData.get('first_name') || '').trim();
            var last = (formData.get('last_name') || '').trim();
            formData.set('full_name', (first + ' ' + last).trim());
            formData.set('user_group', self.defaultGroup || 'Customer');
            formData.set('email', self.pendingEmail || formData.get('email'));

            var actionUrl = form.getAttribute('data-action-url');
            fetch(actionUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': self.getCsrfToken() },
                body: formData
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data.success) {
                        self.showAlert('Account created successfully!', true);
                        self.isUserAuthenticated = true;
                        if (data.csrf_token) {
                            document.querySelectorAll('input[name="csrfmiddlewaretoken"]').forEach(function (input) {
                                input.value = data.csrf_token;
                            });
                        }
                        setTimeout(function () {
                            self.closeModal();
                            if (typeof self.onSuccessCallback === 'function') {
                                self.onSuccessCallback();
                            } else {
                                window.location.reload();
                            }
                        }, 700);
                    } else {
                        self.showAlert(data.message || 'Could not create account.', false);
                    }
                })
                .catch(function () {
                    self.showAlert('Registration failed. Please try again.', false);
                });
        });
    }
};

document.addEventListener('DOMContentLoaded', function () {
    window.GlobalAuth.init();
});
