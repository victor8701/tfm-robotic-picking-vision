


// OmniCore App SDK 1.6.0



// Copyright (c) 2020-2026 ABB

// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software (the "Software"), to deal in the Software without
// restriction, including without limitation the rights to use, copy, modify,
// merge, publish, distribute, sublicense, and/or sell copies of the Software,
// and to permit persons to whom the Software is furnished to do so, subject to
// the following conditions:

// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.

// The manuals related to the Software and the information therein are not
// included in these permissions and must not be reproduced, distributed,
// copied, or disclosed to third parties without ABB's written permission.
// ABB reserves all rights regarding Intellectual Property Rights in such
// manuals and information therein. 

// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
// FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
// DEALINGS IN THE SOFTWARE.





"use strict";

var App = App || {};

if (typeof App.constructed === "undefined") {
    (function(o) {
        o.APP_LIB_VERSION = "1.6.0";
        const init = () => {};
        window.addEventListener("load", init, false);
        o.isTPUWebView = () => {
            return window.THIS_IS_NOT_A_TPU_WEBVIEW != true && ("chrome" in window && "webview" in window.chrome && "postMessage" in window.chrome.webview || "external" in window && "notify" in window.external || "_omnipanel_type_1" in window || "hybridWebViewHost" in window && "sendMessage" in window.hybridWebViewHost);
        };
        const postWebViewMessage = message => {
            if ("chrome" in window && "webview" in window.chrome && "postMessage" in window.chrome.webview) {
                window.chrome.webview.postMessage(message);
            } else if ("external" in window && "notify" in window.external) {
                window.external.notify(message);
            } else if ("_omnipanel_type_1" in window) {
                console.debug(`{{fp-command}}${message}`);
            } else if ("hybridWebViewHost" in window && "sendMessage" in window.hybridWebViewHost) {
                window.hybridWebViewHost.sendMessage(`__RawMessage|${message}`);
            } else {
                throw new Error("Could not post WebView message, WebView not recognized.");
            }
        };
        o.setBusyState = function(state) {
            let busyFlag = "false";
            if (state == true) {
                busyFlag = "true";
            }
            if (o.isTPUWebView()) {
                postWebViewMessage(`IsBusy ${busyFlag}`);
            }
        };
        let onGetAppTypeListeners = [];
        o.getTpuType = function() {
            if (o.isTPUWebView()) {
                let listener = {
                    promise: null,
                    resolve: null,
                    reject: null
                };
                listener.promise = new Promise((resolve, reject) => {
                    listener.resolve = resolve;
                    listener.reject = reject;
                    setTimeout(() => {
                        var temp = [];
                        let length = onGetAppTypeListeners.length;
                        for (let iii = 0; iii < length; iii++) {
                            let item = onGetAppTypeListeners.shift();
                            if (item !== listener) {
                                temp.push(item);
                            }
                        }
                        onGetAppTypeListeners = temp;
                        reject("Request timed out.");
                    }, 3e3);
                });
                onGetAppTypeListeners.push(listener);
                postWebViewMessage("GetTpuType");
                return listener.promise;
            } else {
                let response = JSON.stringify({
                    isTpu: false,
                    machineName: ""
                });
                return Promise.resolve(response);
            }
        };
        o.onGetTpuType = async data => {
            let length = onGetAppTypeListeners.length;
            for (let iii = 0; iii < length; iii++) {
                onGetAppTypeListeners.shift().resolve(data);
            }
        };
        o.Interaction = new function() {
            this.closeApp = function() {
                if (o.isTPUWebView()) {
                    postWebViewMessage("CloseApp");
                }
            };
            let activeMessage = null;
            this.onSendMessageResponse = async data => {
                if (activeMessage === null) {
                    console.log("No active message.");
                }
                activeMessage.resolve(data);
                activeMessage = null;
            };
            this.sendMessage = function(message) {
                const checkMessage = msg => {
                    if (msg.hasOwnProperty("AppName") === false) {
                        console.error(`'AppName' not present in message.`);
                        return false;
                    }
                    if (msg.hasOwnProperty("Message") === false) {
                        console.error(`'Message' not present in message.`);
                        return false;
                    }
                    return true;
                };
                if (o.isTPUWebView()) {
                    if (checkMessage(message) === false) {
                        return Promise.reject("Message is not of supported type.");
                    }
                    let listener = {
                        promise: null,
                        resolve: null,
                        reject: null
                    };
                    listener.promise = new Promise((resolve, reject) => {
                        listener.resolve = resolve;
                        listener.reject = reject;
                        setTimeout(() => {
                            activeMessage = null;
                            reject("Request timed out.");
                        }, 3e3);
                    });
                    activeMessage = listener;
                    let messageString = JSON.stringify(message);
                    postWebViewMessage(`SendMessage ${messageString}`);
                    return listener.promise;
                } else {
                    return Promise.reject("Messages not supported.");
                }
            };
            this.onMessageReceived = async info => {
                let status = "";
                if (typeof appMessageReceived === "function") {
                    try {
                        await Promise.resolve(appMessageReceived(info)).then(x => {
                            if (x == true) return Promise.resolve();
                            return Promise.reject();
                        }).then(() => status = "").catch(() => status = "'appMessageReceived' failed.");
                    } catch (error) {
                        console.error(`onMessageReceived failed to execute, function 'appMessageReceived' may be faulty. >>> ${error}`);
                        status = "'appMessageReceived' failed to execute.";
                    }
                } else {
                    status = "'appMessageReceived' not found.";
                    console.error(status);
                }
                if (o.isTPUWebView()) {
                    postWebViewMessage(`SendMessageResponse ${status}`);
                }
            };
            let activeRequest = null;
            this.onNavigateToResponse = data => {
                if (activeRequest === null) {
                    console.log("No active request.");
                    return Promise.reject("No active request.");
                }
                try {
                    let status = JSON.parse(data);
                    if (status.Success === true) {
                        activeRequest.resolve();
                    } else {
                        let s = `Request failed, '${status.Reason}'.`;
                        console.log(s);
                        activeRequest.reject(s);
                    }
                    activeRequest = null;
                } catch (exception) {
                    activeRequest.reject(exception.message);
                    activeRequest = null;
                    console.error(`Exception: ${exception.message}`);
                }
            };
            this.sendNavigateToRequest = info => {
                if (activeRequest !== null) {
                    console.warn("Request already active.");
                    return Promise.reject("Request already active.");
                }
                if (o.isTPUWebView()) {
                    let listener = {
                        promise: null,
                        resolve: null,
                        reject: null
                    };
                    listener.promise = new Promise((resolve, reject) => {
                        listener.resolve = resolve;
                        listener.reject = reject;
                    });
                    activeRequest = listener;
                    let infoText = JSON.stringify(info);
                    postWebViewMessage(`NavigateTo ${infoText}`);
                    return listener.promise;
                } else {
                    return Promise.reject("No external window.");
                }
            };
            this.onNavigateTo = async info => {
                let navigateToStatus = "";
                if (typeof appNavigateTo === "function") {
                    try {
                        await Promise.resolve(appNavigateTo(info)).then(x => {
                            if (x == true) return Promise.resolve();
                            return Promise.reject();
                        }).then(() => navigateToStatus = "").catch(() => navigateToStatus = "'appNavigateTo' failed.");
                    } catch (error) {
                        console.error("onNavigateTo failed to execute, function 'appNavigateTo' may be faulty.");
                    }
                } else {
                    navigateToStatus = "'appNavigateTo' not found.";
                    console.error(navigateToStatus);
                }
                if (o.isTPUWebView()) {
                    postWebViewMessage(`NavigateToResponse ${navigateToStatus}`);
                }
            };
        }();
        o.Activation = new function() {
            this.onActivate = async () => {
                let activateStatus = "false";
                if (typeof appActivate === "function") {
                    try {
                        await Promise.resolve(appActivate()).then(x => {
                            if (x == true) return Promise.resolve();
                            return Promise.reject();
                        }).then(() => activateStatus = "true").catch(() => activateStatus = "false");
                    } catch (error) {
                        console.error("onActivate failed to execute, function 'appActivate' may be faulty.");
                    }
                } else {
                    activateStatus = "true";
                }
                if (o.isTPUWebView()) {
                    postWebViewMessage(`Activated ${activateStatus}`);
                }
            };
            this.onDeactivate = async () => {
                let deactivateStatus = "false";
                if (typeof appDeactivate === "function") {
                    try {
                        await Promise.resolve(appDeactivate()).then(x => {
                            if (x == true) return Promise.resolve();
                            return Promise.reject();
                        }).then(() => deactivateStatus = "true").catch(() => deactivateStatus = "false");
                    } catch (error) {
                        console.error("onDeactivate failed to execute, function 'appDeactivate' may be faulty.");
                    }
                } else {
                    deactivateStatus = "true";
                }
                if (o.isTPUWebView()) {
                    postWebViewMessage(`Deactivated ${deactivateStatus}`);
                }
            };
        }();
        o.constructed = true;
    })(App);
    window["_onGetTpuType"] = App.onGetTpuType;
    window["_onNavigateTo"] = App.Interaction.onNavigateTo;
    window["_onNavigateToResponse"] = App.Interaction.onNavigateToResponse;
    window["_onSendMessage"] = App.Interaction.onMessageReceived;
    window["_onSendMessageResponse"] = App.Interaction.onSendMessageResponse;
    window["_onActivate"] = App.Activation.onActivate;
    window["_onDeactivate"] = App.Activation.onDeactivate;
}