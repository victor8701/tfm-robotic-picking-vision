


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

var RWS = RWS || {};

if (typeof RWS.constructedMain === "undefined") {
    (function(o) {
        o.RWS_LIB_VERSION = "1.6.0";
        const HTTP_REQUEST_TIMEOUT = 3e4;
        const COMMON_TIMEOUT = 120;
        const VC_NOT_SUPPORTED = "Not supported on virtual controller.";
        const SHARED_TAG = "%%SHARED%%";
        const UNASSIGNED_TAG = "%%UNASSIGNED%%";
        let debugType = 1;
        let debugSeverity = 2;
        let isVirtualResult = null;
        let isVirtualResolvers = [];
        let isSpocResult = null;
        let isSpocResolvers = [];
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
        o.isVirtualController = async () => {
            if (isVirtualResult === null) {
                const promise = new Promise(resolve => {
                    isVirtualResolvers.push(resolve);
                });
                await promise;
            }
            return isVirtualResult;
        };
        o.isSpocSystem = async () => {
            if (isSpocResult === null) {
                const promise = new Promise(resolve => {
                    isSpocResolvers.push(resolve);
                });
                await promise;
            }
            return isSpocResult;
        };
        o.init = async () => {
            await (async () => {
                try {
                    const res = await o.Network.get("/ctrl");
                    let obj = null;
                    try {
                        obj = JSON.parse(res.responseText);
                    } catch (error) {
                        throw "Could not parse JSON.";
                    }
                    for (const item of obj._embedded.resources) {
                        if (item._type === "ctrl-identity-info-li") {
                            isVirtualResult = item["ctrl-type"] === "Virtual Controller";
                            window.setTimeout(() => {
                                for (const resolver of isVirtualResolvers) {
                                    resolver();
                                }
                                isVirtualResolvers = [];
                            }, 0);
                            break;
                        }
                    }
                    if (isVirtualResult === null) {
                        throw "No controller type found.";
                    }
                } catch (err) {
                    console.error(`Init failed to read controller type. >>> ${err}`);
                }
            })();
            await (async () => {
                try {
                    const res = await o.Network.get("/rw/system");
                    let obj = null;
                    try {
                        obj = JSON.parse(res.responseText);
                    } catch (error) {
                        throw "Could not parse JSON.";
                    }
                    isSpocResult = Number.parseInt(obj.state[0]["major"]) >= 8;
                    window.setTimeout(() => {
                        for (const resolver of isSpocResolvers) {
                            resolver();
                        }
                        isSpocResolvers = [];
                    }, 0);
                } catch (err) {
                    console.error(`Init failed to read controller type. >>> ${err}`);
                }
            })();
            o.Network.heartBeat();
            if (o.isTPUWebView()) {
                postWebViewMessage("GetCookies");
            }
        };
        window.addEventListener("load", o.init, false);
        o.__unload = false;
        let cleanupStarted = false;
        let creatingSubscriptionGroupAndWebSocket = null;
        const initiateCleanup = async function(initiatedByTPU = true) {
            if (cleanupStarted) {
                return;
            }
            let cleanupStatus = "true";
            if (initiatedByTPU) {
                if (typeof appCleanUp === "function") {
                    try {
                        cleanupStatus = await appCleanUp() ? "true" : "false";
                    } catch (error) {
                        cleanupStatus = "false";
                        console.error("onCleanUp failed to execute, function 'appCleanUp' may be faulty.");
                    }
                }
            }
            if (!cleanupStarted) {
                cleanupStarted = true;
                if (initiatedByTPU) {
                    await creatingSubscriptionGroupAndWebSocket;
                }
                let res;
                res = o.Mastership.releaseAll();
                if (initiatedByTPU) {
                    try {
                        await res;
                    } catch (error) {
                        console.error("Mastership.releaseAll failed. " + JSON.stringify(error));
                    }
                }
                res = o.MotionMastership.releaseAll();
                if (initiatedByTPU) {
                    try {
                        await res;
                    } catch (error) {
                        console.error("MotionMastership.releaseAll failed. " + JSON.stringify(error));
                    }
                }
                o.__unload = true;
                res = o.Subscriptions.unsubscribeToAll();
                if (initiatedByTPU) {
                    try {
                        await res;
                    } catch (error) {
                        console.error("Subscriptions.unsubscribeToAll failed. " + JSON.stringify(error));
                    }
                    postWebViewMessage(`CleanedUp ${cleanupStatus}`);
                }
            }
        };
        window["_onAppSDKCleanup"] = initiateCleanup;
        window.addEventListener("beforeunload", () => {
            initiateCleanup(false);
            return null;
        }, false);
        function encodePath(path) {
            let s = path.split("/");
            let p = "";
            for (let item of s) {
                p += encodeURIComponent(item) + "/";
            }
            return p.slice(0, -1);
        }
        function rejectWithStatus(message, item = {}) {
            let r = createStatusObject(message, item);
            return Promise.reject(r);
        }
        function createStatusObject(message, item = {}) {
            let r = {};
            try {
                let msg = "";
                if (typeof message === "string" && message !== null) msg = message;
                r.message = msg;
                if (typeof item === "Error") {
                    if (r.message.length <= 0) r.message = `Exception: ${item.message}`; else r.message += ` >>> Exception: ${item.message}`;
                } else if (typeof item === "string") {
                    if (r.message.length <= 0) r.message = item; else r.message += ` >>> ${item}`;
                } else if (item.hasOwnProperty("message")) {
                    r = JSON.parse(JSON.stringify(item));
                    r.message = msg;
                    if (typeof item.message === "string" && item.message.length > 0) r.message += ` >>> ${item.message}`;
                }
            } catch (error) {
                r = {};
                r.message = `Failed to create status object. >>> Exception: ${error.message}`;
            }
            return r;
        }
        o.setDebug = (dtype = 0, severity = 2) => {
            debugType = dtype;
            debugSeverity = severity;
        };
        o.isDebugActive = x => {
            return x >= debugSeverity;
        };
        o.writeDebug = (text, severity = 0) => {
            if (debugSeverity > severity) return;
            const getFileRef = stack => {
                let splits = stack.split("\n");
                let s = "";
                for (let iii = 2; iii < splits.length; iii++) {
                    s = splits[iii].trim();
                    if (s !== "at Promise (native code)") break;
                }
                return s.slice(3);
            };
            let t = "";
            if (debugType === 1) {
                t = text;
            } else if (debugType === 2) {
                let s = getFileRef(new Error().stack);
                t = `${text}   [${s}]`;
            } else if (debugType === 3) {
                if (severity >= 3) {
                    let errStack = new Error().stack;
                    let splits = errStack.split("\n");
                    let s = "";
                    for (let iii = 2; iii < splits.length; iii++) {
                        s += "   " + splits[iii].trim().slice(3) + "\n";
                    }
                    t = `${text}\nCall stack:\n${s.trim()}`;
                } else {
                    let s = getFileRef(new Error().stack);
                    t = `${text}   [${s}]`;
                }
            }
            if (debugType > 0) {
                if (severity === 0) {
                    console.log(t);
                } else if (severity === 1) {
                    console.info(t);
                } else if (severity === 2) {
                    console.warn(t);
                } else if (severity === 3) {
                    console.error(t);
                }
            }
        };
        const isNonEmptyString = x => {
            if (x === null) return false;
            if (typeof x !== "string") return false;
            if (x === "") return false;
            return true;
        };
        function verifyDataType(data, reference) {
            if (data === Object(data)) {
                if (reference !== Object(reference)) {
                    return "Unexpected data type.";
                }
                let s = "";
                for (let item of Object.keys(data)) {
                    if (reference.hasOwnProperty(item) === true) {
                        if (typeof data[item] !== typeof reference[item]) {
                            s += `Unexpected data type, property '${item}'\n`;
                        }
                    } else {
                        s += `Unexpected property '${item}'\n`;
                    }
                }
                if (s.length > 0) s = s.slice(0, -1);
                return s;
            } else {
                if (typeof data !== typeof reference) {
                    return "Unexpected data type.";
                }
            }
            return "";
        }
        var errorCodeCache = {};
        function verifyReturnCode(json) {
            return new Promise((resolve, reject) => {
                try {
                    if (json.hasOwnProperty("state") === false) return resolve(undefined);
                    let errors = [];
                    let returnValues = {};
                    for (let iii = 0; iii < json.state.length; iii++) {
                        let item = json.state[iii];
                        for (let subitem in item) {
                            if (item[subitem].hasOwnProperty("_links")) {
                                let x1 = item[subitem]["_links"];
                                if (x1.hasOwnProperty("error")) {
                                    let x2 = x1["error"];
                                    if (x2.hasOwnProperty("href")) {
                                        let errUrl = x2["href"];
                                        if (errorCodeCache.hasOwnProperty(errUrl)) {
                                            returnValues[subitem] = errorCodeCache[errUrl];
                                            continue;
                                        }
                                        errors.push(o.Network.get(errUrl).then(x => {
                                            let obj = getReponseAsJSON(x);
                                            let r = {
                                                name: obj.state[0].name,
                                                code: obj.state[0].code,
                                                severity: obj.state[0].severity,
                                                description: obj.state[0].description
                                            };
                                            errorCodeCache[errUrl] = r;
                                            returnValues[subitem] = r;
                                            return Promise.resolve();
                                        }).catch(err => {
                                            let errStr = `Failed to get error code, url '${errUrl}'. >>> ${err}`;
                                            o.writeDebug(errStr, 3);
                                            return Promise.resolve();
                                        }));
                                    }
                                }
                            }
                        }
                    }
                    if (errors.length > 0) {
                        return Promise.all(errors).then(() => reject(returnValues));
                    }
                    if (Object.keys(returnValues).length > 0) {
                        return reject(returnValues);
                    }
                    return resolve(undefined);
                } catch (error) {
                    o.writeDebug(`Failed to get error code. >>> ${error}`, 2);
                    return resolve(undefined);
                }
                return resolve(undefined);
            });
        }
        function verfifyErrorCode(text) {
            let code = "";
            try {
                let obj = parseJSON(text);
                if (typeof obj !== "undefined") {
                    if (obj.hasOwnProperty("status") === false || obj.status.hasOwnProperty("code") === false) throw new Error("JSON does not include status code.");
                    code = obj.status.code;
                } else {
                    o.writeDebug(`Could not parse JSON error code. >>> ${text}`, 2);
                    if (text.startsWith("<?xml") === true) {
                        let parser = new DOMParser();
                        let data = parser.parseFromString(text, "text/xml");
                        let items = data.getElementsByTagName("div")[0].getElementsByTagName("span");
                        for (let iii = 0; iii < items.length; iii++) {
                            let className = items[iii].getAttribute("class");
                            if (className === "code") {
                                code = items[iii].innerHTML;
                                break;
                            }
                        }
                    } else {
                        let idx1 = text.indexOf('"code":');
                        let idx2 = text.indexOf(', "msg":');
                        if (idx1 >= 0 && idx2 >= 0 && idx2 > idx1) {
                            code = text.substring(idx1 + 7, idx2);
                        }
                    }
                    if (code == "") return Promise.resolve(undefined);
                }
            } catch (error) {
                let errStr = `Failed to get error code. >>> ${error}`;
                o.writeDebug(errStr, 0);
                return Promise.reject(errStr);
            }
            return getStatusCode(code);
        }
        function getStatusCode(code) {
            let url = `/rw/retcode?code=${encodeURIComponent(code)}`;
            if (errorCodeCache.hasOwnProperty(url)) {
                return Promise.resolve(errorCodeCache[url]);
            } else {
                return o.Network.get(url).then(x => {
                    let obj = getReponseAsJSON(x);
                    let r = {
                        name: obj.state[0].name,
                        code: obj.state[0].code,
                        severity: obj.state[0].severity,
                        description: obj.state[0].description
                    };
                    errorCodeCache[url] = r;
                    return Promise.resolve(r);
                }).catch(err => {
                    let errStr = `Failed to get error code, url '${errUrl}'. >>> ${err}`;
                    o.writeDebug(errStr, 3);
                    return Promise.reject(errStr);
                });
            }
        }
        function getReponseAsJSON(request) {
            return parseJSON(request.responseText);
        }
        function parseJSON(json) {
            try {
                return JSON.parse(json);
            } catch (error) {
                o.writeDebug(`Failed to parse JSON. >>> ${error}`, 0);
                return undefined;
            }
        }
        function requestMastership() {
            return o.Mastership.request().then(() => Promise.resolve()).catch(err => Promise.reject(rejectWithStatus("Could not get Mastership.", err)));
        }
        function releaseMastership() {
            return o.Mastership.release().then(() => Promise.resolve()).catch(err => {
                o.writeDebug(`Could not release Mastership. >>> ${err.message}`);
                return Promise.resolve();
            });
        }
        function requestMotionMastership() {
            return o.MotionMastership.request().then(() => Promise.resolve()).catch(err => Promise.reject(rejectWithStatus("Could not get motion mastership.", err)));
        }
        function releaseMotionMastership() {
            return o.MotionMastership.release().then(() => Promise.resolve()).catch(err => {
                o.writeDebug(`Could not release motion mastership. >>> ${err.message}`);
                return Promise.resolve();
            });
        }
        function waitProgressCompletion(location, timeout = 60) {
            if (isNaN(timeout) == true || timeout < 0) return Promise.reject("timeout not valid.");
            const checkProgress = loops => {
                if (loops <= 0) {
                    let s = `${location} did not complete within ${timeout}s.`;
                    return Promise.reject(s);
                }
                const wait1s = () => new Promise(resolve => setTimeout(resolve, 1e3));
                return wait1s().then(() => {
                    return o.Network.get(location).then(res2 => {
                        let json2 = parseJSON(res2.responseText);
                        if (typeof json2 === "undefined") return Promise.reject();
                        let code = 0;
                        let ready = false;
                        for (const item of json2.state) {
                            if (item._type === "progress" && item.state === "ready") {
                                ready = true;
                                code = item.code;
                                break;
                            }
                        }
                        if (ready === true) return Promise.resolve(code); else return Promise.reject();
                    });
                }).then(x1 => {
                    return Promise.resolve(x1);
                }).catch(() => {
                    return checkProgress(loops - 1);
                });
            };
            return checkProgress(timeout);
        }
        o.Rapid = new function() {
            this.MonitorResources = {
                execution: "execution",
                programPointer: "program-pointer",
                motionPointer: "motion-pointer",
                uiInstruction: "uiinstr"
            };
            this.RegainModes = {
                continue: "continue",
                regain: "regain",
                clear: "clear",
                enterConsume: "enter_consume"
            };
            this.ExecutionModes = {
                continue: "continue",
                stepIn: "step_in",
                stepOver: "step_over",
                stepOut: "step_out",
                stepBackwards: "step_backwards",
                stepToLast: "step_to_last",
                stepToMotion: "step_to_motion"
            };
            this.CycleModes = {
                forever: "forever",
                asIs: "as_is",
                once: "once"
            };
            this.Conditions = {
                none: "none",
                callChain: "callchain"
            };
            this.StopModes = {
                cycle: "cycle",
                instruction: "instruction",
                stop: "stop",
                quickStop: "quick_stop"
            };
            this.UseTSPOptions = {
                normal: "normal",
                allTasks: "all_tasks"
            };
            this.SearchMethods = {
                block: 1,
                scope: 2
            };
            this.SymbolTypes = {
                undefined: 0,
                constant: 1,
                variable: 2,
                persistent: 4,
                function: 8,
                procedure: 16,
                trap: 32,
                module: 64,
                task: 128,
                routine: 8 + 16 + 32,
                rapidData: 1 + 2 + 4,
                any: 255
            };
            this.ExecutionStates = {
                running: "running",
                stopped: "stopped"
            };
            this.UiinstrEvents = {
                send: "send",
                post: "post",
                abort: "abort"
            };
            this.UiinstrExecLevels = {
                user: "user",
                normal: "normal"
            };
            this.TaskTypes = {
                normal: "normal",
                static: "static",
                semistatic: "semistatic",
                unknown: "unknown"
            };
            this.TaskStates = {
                empty: "empty",
                initiated: "initiated",
                linked: "linked",
                loaded: "loaded",
                uninitialized: "uninitialized"
            };
            this.TaskExecutionStates = {
                ready: "ready",
                stopped: "stopped",
                started: "started",
                uninitialized: "uninitialized"
            };
            this.TaskActiveStates = {
                on: "on",
                off: "off"
            };
            this.TaskTrustLevels = {
                sys_fail: "sys_fail",
                sys_halt: "sys_halt",
                sys_stop: "sys_stop",
                none: "none"
            };
            this.TaskExecutionLevels = {
                none: "none",
                normal: "normal",
                trap: "trap",
                user: "user",
                unknown: "unknown"
            };
            this.TaskExecutionModes = {
                continous: "continous",
                step_over: "step_over",
                step_in: "step_in",
                step_out_of: "step_out_of",
                step_back: "step_back",
                step_last: "step_last",
                stepwise: "stepwise",
                unknown: "unknown"
            };
            this.TaskExecutionTypes = {
                none: "none",
                normal: "normal",
                interrupt: "interrupt",
                external_interrupt: "external_interrupt",
                user_routine: "user_routine",
                event_routine: "event_routine",
                unknown: "unknown"
            };
            this.DataSymbolTypes = {
                constant: "constant",
                variable: "variable",
                persistent: "persistent"
            };
            this.DataScopes = {
                local: "local",
                task: "task",
                global: "global"
            };
            let abortingServiceRoutine = false;
            function Monitor(resource, task = "") {
                if (typeof resource !== "string" || resource.toLowerCase() !== o.Rapid.MonitorResources.execution && resource.toLowerCase() !== o.Rapid.MonitorResources.programPointer && resource.toLowerCase() !== o.Rapid.MonitorResources.motionPointer && resource.toLowerCase() !== o.Rapid.MonitorResources.uiInstruction) {
                    o.writeDebug("Unable to create Rapid Monitor: Illegal resource.", 3);
                    return;
                }
                if (task === null || resource !== o.Rapid.MonitorResources.execution && resource !== o.Rapid.MonitorResources.uiInstruction && task === "") {
                    o.writeDebug("Unable to create Monitor: Illegal task.", 3);
                    return;
                }
                let resourceName = resource;
                const urls = {
                    execution: "/rw/rapid/execution",
                    "program-pointer": `/rw/rapid/tasks/${encodeURIComponent(task)}/pcp`,
                    "motion-pointer": `/rw/rapid/tasks/${encodeURIComponent(task)}/pcp`,
                    uiinstr: "/rw/rapid/uiinstr/active"
                };
                const resourceStrings = {
                    execution: "/rw/rapid/execution;ctrlexecstate",
                    "program-pointer": `/rw/rapid/tasks/${encodeURIComponent(task)}/pcp;programpointerchange`,
                    "motion-pointer": `/rw/rapid/tasks/${encodeURIComponent(task)}/pcp;motionpointerchange`,
                    uiinstr: "/rw/rapid/uiinstr;uievent"
                };
                var callbacks = [];
                this.getTitle = function() {
                    return urls[resourceName];
                };
                this.getResourceString = function() {
                    return resourceStrings[resourceName];
                };
                this.addCallbackOnChanged = function(callback) {
                    if (typeof callback !== "function") throw new Error("callback is not a valid function");
                    callbacks.push(callback);
                };
                this.onchanged = async function(newValue) {
                    let parsedValue = {};
                    switch (resourceName) {
                      case "execution":
                        if (newValue.hasOwnProperty("ctrlexecstate")) parsedValue = newValue["ctrlexecstate"];
                        break;

                      case "program-pointer":
                      case "motion-pointer":
                        let pp = {};
                        pp["moduleName"] = newValue.hasOwnProperty("module-name") ? newValue["module-name"] : "";
                        pp["routineName"] = newValue.hasOwnProperty("routine-name") ? newValue["routine-name"] : "";
                        pp["beginPosition"] = newValue.hasOwnProperty("BegPosLine") ? newValue.BegPosLine : "";
                        if (newValue.hasOwnProperty("BegPosCol")) {
                            pp["beginPosition"] += "," + newValue.BegPosCol;
                        }
                        if (pp["beginPosition"] === "0,0") {
                            pp["beginPosition"] = "";
                        }
                        pp["endPosition"] = newValue.hasOwnProperty("EndPosLine") ? newValue.EndPosLine : "";
                        if (newValue.hasOwnProperty("EndPosCol")) {
                            pp["endPosition"] += "," + newValue.EndPosCol;
                        }
                        if (pp["endPosition"] === "0,0") {
                            pp["endPosition"] = "";
                        }
                        pp["hasValue"] = pp["moduleName"] !== "" || pp["routineName"] !== "" || pp["beginPosition"] !== "" || pp["endPosition"] !== "";
                        parsedValue = pp;
                        break;

                      case "uiinstr":
                        let t = null;
                        try {
                            t = await processUIInstr(newValue);
                        } catch (error) {
                            o.writeDebug(`processUIInstr failed. >>> ${error.toString()}`, 2);
                        }
                        parsedValue = t;
                        break;

                      default:
                        o.writeDebug(`Unhandled event, '${JSON.stringify(newValue)}'`);
                        return;
                    }
                    for (let iii = 0; iii < callbacks.length; iii++) {
                        try {
                            callbacks[iii](parsedValue);
                        } catch (error) {
                            o.writeDebug(`Rapid.Monitor callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                const processUIInstr = async uiinstr => {
                    if (uiinstr.hasOwnProperty("instr") === false || uiinstr.hasOwnProperty("event") === false) {
                        o.writeDebug(`Unhandled uiinstr event, '${JSON.stringify(uiinstr)}'`);
                        return;
                    }
                    if (uiinstr["instr"] === "UIMsgWrite") {
                        o.writeDebug(`Unhandled uiinstr event, 'UIMsgWrite' not supported`);
                        return;
                    }
                    let stack = uiinstr["stack"].split("/");
                    let data = {
                        instruction: uiinstr["instr"],
                        event: uiinstr["event"].toLowerCase(),
                        task: stack[1],
                        message: uiinstr["msg"].replace(/^"/g, "").replace(/"$/g, ""),
                        executionLevel: uiinstr["execlv"].toLowerCase()
                    };
                    switch (uiinstr["event"]) {
                      case "POST":
                        data["id"] = "";
                        break;

                      case "SEND":
                        data["id"] = stack[2].slice(2);
                        let t = `/rw/rapid/uiinstr/active/params/RAPID/${data.task}/%$${data.id}`;
                        let callUrl = encodePath(t);
                        await o.Network.get(callUrl).then(res => {
                            let obj = parseJSON(res.responseText);
                            if (typeof obj === "undefined") return o.writeDebug("Could not parse JSON.");
                            let parameters = {};
                            for (const item of obj._embedded.resources) {
                                let val = getUIInstrData(item);
                                if (val !== null) parameters[item._title] = val;
                            }
                            data["parameters"] = parameters;
                        }).catch(err => o.writeDebug(`Failed to get parameters for uiinstr event for instruction '${uiinstr["instr"]}' >>> ${err}`, 2));
                        break;

                      case "ABORT":
                        data["id"] = stack[2].slice(2);
                        break;

                      default:
                        o.writeDebug(`Unsupported uiinstr event '${uiinstr["event"]}' for instruction '${uiinstr["instr"]}'`);
                        return;
                    }
                    return data;
                };
                const getUIInstrData = item => {
                    if (item.hasOwnProperty("_type") === false || item._type !== "rap-uiparams-li") return null;
                    if (item.hasOwnProperty("_title") === false) return null;
                    if (item.value === null) return null;
                    let symbol = null;
                    switch (item._title) {
                      case "Buttons":
                      case "Icon":
                      case "MaxTime":
                      case "BreakFlag":
                      case "TPAnswer":
                      case "InitValue":
                      case "MinValue":
                      case "MaxValue":
                      case "Increment":
                      case "ResultIndex":
                        symbol = parseFloat(item.value);
                        break;

                      case "TPCompleted":
                      case "Wrap":
                      case "DIpass":
                      case "DOpass":
                      case "PersBoolPassive":
                      case "AsInteger":
                        symbol = item.value.toUpperCase() == "TRUE";
                        break;

                      case "Result":
                      case "Header":
                      case "Image":
                      case "InstrUsingIMessageBox":
                      case "TPText":
                      case "TPFK1":
                      case "TPFK2":
                      case "TPFK3":
                      case "TPFK4":
                      case "TPFK5":
                      case "InitString":
                        symbol = item.value.replace(/^"/g, "").replace(/"$/g, "");
                        break;

                      case "MsgArray":
                      case "BtnArray":
                      case "ListItems":
                        symbol = JSON.parse(item.value);
                        break;

                      default:
                        o.writeDebug(`Unhandled symbol type '${item._title}'`);
                        return null;
                    }
                    return symbol;
                };
                const raiseEvent = async () => {
                    const getValue = async () => {
                        let rawValue = await o.Network.get(urls[resourceName]).then(x1 => {
                            let obj = parseJSON(x1.responseText);
                            if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                            return obj;
                        }).catch(err => {
                            if (err.hasOwnProperty("httpStatus") && err.httpStatus.hasOwnProperty("code") && err.httpStatus.code !== 404) {
                                let s = JSON.stringify(err);
                                o.writeDebug(`Rapid.raiseEvent failed getting value. >>> ${s}`);
                            }
                            return null;
                        });
                        if (rawValue === null) return null;
                        let parsedValue = null;
                        switch (resourceName) {
                          case "execution":
                            if (rawValue.hasOwnProperty("state") && rawValue["state"].length > 0) {
                                let state = rawValue["state"][0];
                                if (state.hasOwnProperty("ctrlexecstate")) {
                                    parsedValue = state["ctrlexecstate"];
                                }
                            }
                            break;

                          case "program-pointer":
                          case "motion-pointer":
                            let pointers = parsePointers(rawValue);
                            if (resourceName === "program-pointer") {
                                parsedValue = pointers.programPointer;
                            } else {
                                parsedValue = pointers.motionPointer;
                            }
                            break;

                          case "uiinstr":
                            if (rawValue.hasOwnProperty("state")) parsedValue = await processUIInstr(rawValue.state[0]);
                            break;

                          default:
                            o.writeDebug(`Unsupported resource '${resourceName}'`);
                            break;
                        }
                        return parsedValue;
                    };
                    let value = await getValue();
                    if (value === null) return;
                    for (let iii = 0; iii < callbacks.length; iii++) {
                        try {
                            callbacks[iii](value);
                        } catch (error) {
                            o.writeDebug(`Rapid.Monitor callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                this.subscribe = function(raiseInitial = false) {
                    if (raiseInitial === true) return o.Subscriptions.subscribe([ this ], raiseEvent);
                    return o.Subscriptions.subscribe([ this ]);
                };
                this.unsubscribe = function() {
                    return o.Subscriptions.unsubscribe([ this ]);
                };
            }
            this.getMonitor = function(resource, taskName) {
                return new Monitor(resource, taskName);
            };
            function Task(name) {
                var taskName = name;
                var taskType = null;
                var taskState = null;
                var executionState = null;
                var activeState = null;
                var isMotionTask = null;
                var trustLevel = null;
                var id = null;
                var executionLevel = null;
                var executionMode = null;
                var executionType = null;
                var progEntrypoint = null;
                var bindRef = null;
                var taskInForeground = null;
                this.getName = function() {
                    return taskName;
                };
                this.getProperties = function() {
                    return refreshProperties().then(() => {
                        var properties = {
                            name: taskName,
                            taskType: taskType,
                            taskState: taskState,
                            executionState: executionState,
                            activeState: activeState,
                            isMotionTask: isMotionTask,
                            trustLevel: trustLevel,
                            id: id,
                            executionLevel: executionLevel,
                            executionMode: executionMode,
                            executionType: executionType,
                            progEntrypoint: progEntrypoint,
                            bindRef: bindRef,
                            taskInForeground: taskInForeground
                        };
                        return Promise.resolve(properties);
                    }).catch(err => Promise.reject(err));
                };
                function ServiceRoutine(urlToRoutine) {
                    var routineUrl = urlToRoutine;
                    var routineName = "";
                    (function() {
                        let splits = routineUrl.split("/");
                        routineName = splits.pop();
                    })();
                    this.getName = function() {
                        return routineName;
                    };
                    this.getUrl = function() {
                        return routineUrl;
                    };
                    this.setPP = async function() {
                        const callUrl = encodePath(`/rw/rapid/tasks/${taskName}/pcp/routine`);
                        const body = `routine=${encodeURIComponent(routineName)}&userlevel=TRUE`;
                        const ERR_MSG = "Failed to set PP to service routine.";
                        try {
                            await o.Mastership.request();
                        } catch (e) {
                            throw createStatusObject(ERR_MSG, e);
                        }
                        try {
                            await o.Network.post(callUrl, body);
                        } catch (e) {
                            throw createStatusObject(ERR_MSG, e);
                        } finally {
                            try {
                                await o.Mastership.release();
                            } catch (e) {}
                        }
                    };
                }
                this.getServiceRoutines = function() {
                    let callUrl = `/rw/rapid/tasks/${taskName}/serviceroutine`;
                    return o.Network.get(callUrl).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        let serviceRoutines = [];
                        for (const item of obj.state) {
                            if (item._type === "rap-task-routine" && item["service-routine"] === "TRUE") {
                                if (item.hasOwnProperty("url-to-routine") === false) continue;
                                let sr = new ServiceRoutine(item["url-to-routine"]);
                                serviceRoutines.push(sr);
                            }
                        }
                        return Promise.resolve(serviceRoutines);
                    }).catch(err => rejectWithStatus("Failed to get service routines.", err));
                };
                this.getData = function(moduleName, symbolName) {
                    return RWS.Rapid.getData(taskName, moduleName, symbolName);
                };
                var refreshProperties = function() {
                    const replacables = {
                        SysFail: "sys_fail",
                        SysHalt: "sys_halt",
                        SysStop: "sys_stop",
                        StepOver: "step_over",
                        StepIn: "step_in",
                        StepOutOf: "step_out_of",
                        StepBack: "step_back",
                        StepLast: "step_last",
                        StepWise: "stepwise",
                        Inter: "interrupt",
                        ExInter: "external_interrupt",
                        UsRout: "user_routine",
                        EvRout: "event_routine"
                    };
                    const processString = function(text) {
                        if (typeof text !== "string" || text === null) return "";
                        if (replacables.hasOwnProperty(text) === false) return text.toLowerCase();
                        return replacables[text];
                    };
                    return o.Network.get(`/rw/rapid/tasks/${encodeURIComponent(taskName)}`).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        let itemFound = false;
                        for (const item of obj.state) {
                            if (item._type === "rap-task") {
                                taskType = processString(item.type);
                                taskState = processString(item.taskstate);
                                executionState = processString(item.excstate);
                                activeState = processString(item.active);
                                if (item.hasOwnProperty("motiontask")) {
                                    isMotionTask = item.motiontask.toLowerCase() === "true";
                                } else {
                                    isMotionTask = false;
                                }
                                trustLevel = processString(item.trust);
                                id = parseInt(item.taskID);
                                executionLevel = processString(item.execlevel);
                                executionMode = processString(item.execmode);
                                executionType = processString(item.exectype);
                                progEntrypoint = item.prodentrypt;
                                if (item.hasOwnProperty("bind_ref")) {
                                    bindRef = item.bind_ref.toLowerCase() === "true";
                                } else {
                                    bindRef = false;
                                }
                                taskInForeground = item.task_in_forgnd;
                                itemFound = true;
                                break;
                            }
                        }
                        if (itemFound === false) {
                            return Promise.reject("Could not find symbol rap-task value in RWS response");
                        }
                        return Promise.resolve("Success");
                    }).catch(err => rejectWithStatus("Failed getting properties.", err));
                };
                this.getProgramInfo = function() {
                    return o.Network.get(`/rw/rapid/tasks/${encodeURIComponent(taskName)}/program`).then(res => {
                        if (typeof res.responseText == "undefined" || res.responseText === "") {
                            return Promise.resolve({
                                name: "",
                                entrypoint: ""
                            });
                        }
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        let programInfo = {};
                        for (const item of obj.state) {
                            if (item._type === "rap-program") {
                                programInfo.name = item.name;
                                programInfo.entrypoint = item.entrypoint;
                            }
                        }
                        return Promise.resolve(programInfo);
                    }).catch(err => rejectWithStatus("Failed getting program info.", err));
                };
                this.getModuleNames = function() {
                    return o.Network.get(`/rw/rapid/tasks/${encodeURIComponent(taskName)}/modules`).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        let modules = {};
                        modules.programModules = [];
                        for (const item of obj.state) {
                            if (item._type === "rap-module-info-li" && item.type === "ProgMod") {
                                modules.programModules.push(item.name);
                            }
                        }
                        modules.systemModules = [];
                        for (const item of obj.state) {
                            if (item._type === "rap-module-info-li" && item.type === "SysMod") {
                                modules.systemModules.push(item.name);
                            }
                        }
                        return Promise.resolve(modules);
                    }).catch(err => rejectWithStatus("Failed getting module name.", err));
                };
                this.getModule = function(moduleName) {
                    return RWS.Rapid.getModule(taskName, moduleName);
                };
                this.movePPToRoutine = async function(routineName, userLevel = false, moduleName = undefined) {
                    if (typeof routineName !== "string") throw "Parameter 'routineName' is not a string.";
                    if (typeof userLevel !== "boolean") throw "Parameter 'userLevel' is not a boolean.";
                    const ERR_MSG = "Failed to set PP to routine.";
                    const callUrl = `/rw/rapid/tasks/${encodeURIComponent(taskName)}/pcp/routine`;
                    const moduleArg = moduleName ? `&module=${encodeURIComponent(moduleName)}` : "";
                    const body = `routine=${encodeURIComponent(routineName)}${moduleArg}&userlevel=${encodeURIComponent(userLevel.toString())}`;
                    try {
                        await o.Mastership.request();
                    } catch (e) {
                        throw createStatusObject(ERR_MSG, e);
                    }
                    try {
                        await o.Network.post(callUrl, body);
                    } catch (e) {
                        throw createStatusObject(ERR_MSG, e);
                    } finally {
                        try {
                            await o.Mastership.release();
                        } catch (e) {}
                    }
                };
                this.abortServiceRoutine = async () => {
                    const ERR_MSG = "Could not abort service routine.";
                    if (abortingServiceRoutine) {
                        throw createStatusObject(ERR_MSG, "Abort process already in progress.");
                    }
                    abortingServiceRoutine = true;
                    try {
                        await o.Mastership.request();
                    } catch (e) {
                        this.abortServiceRoutine = false;
                        throw createStatusObject(ERR_MSG, e);
                    }
                    try {
                        let props = await this.getProperties();
                        if (props.executionLevel === o.Rapid.TaskExecutionLevels.user) {
                            await o.Network.post(`/rw/rapid/tasks/${encodeURIComponent(taskName)}/abortexeclevel`);
                        } else {
                            throw 'Current execution level is not "user".';
                        }
                    } catch (e) {
                        throw createStatusObject(ERR_MSG, e);
                    } finally {
                        try {
                            await o.Mastership.release();
                        } catch (e) {}
                        abortingServiceRoutine = false;
                    }
                };
                this.getPointers = function() {
                    let callUrl = `/rw/rapid/tasks/${encodeURIComponent(taskName)}/pcp`;
                    return o.Network.get(callUrl).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        let pcp = parsePointers(obj);
                        return Promise.resolve(pcp);
                    }).catch(err => rejectWithStatus("Failed getting pointers.", err));
                };
            }
            function Module(task, module) {
                var taskName = isNonEmptyString(task) === true ? task : "";
                var moduleName = isNonEmptyString(module) === true ? module : "";
                var fileName = null;
                var attributes = null;
                this.getName = function() {
                    return moduleName;
                };
                this.getTaskName = function() {
                    return taskName;
                };
                this.getFileName = function() {
                    return fileName;
                };
                this.getAttributes = function() {
                    return attributes;
                };
                this.getProperties = function() {
                    return refreshProperties().then(() => {
                        var properties = {
                            taskName: taskName,
                            moduleName: moduleName,
                            fileName: fileName,
                            attributes: attributes
                        };
                        return Promise.resolve(properties);
                    }).catch(err => Promise.reject(err));
                };
                this.getData = function(symbolName) {
                    return new Data(taskName, moduleName, symbolName);
                };
                var refreshProperties = function() {
                    let url = `/rw/rapid/tasks/${encodeURIComponent(taskName)}/modules/${encodeURIComponent(moduleName)}`;
                    return o.Network.get(url).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        let itemFound = false;
                        for (const item of obj.state) {
                            if (item._type === "rap-module") {
                                fileName = item.filename;
                                attributes = item.attribute;
                                itemFound = true;
                                break;
                            }
                        }
                        if (itemFound === false) {
                            return Promise.reject("Could not find symbol rap-module value in RWS response");
                        }
                        return Promise.resolve("Success");
                    }).catch(err => rejectWithStatus("Failed getting properties.", err));
                };
            }
            function Data(task, module, symbol) {
                var taskName = isNonEmptyString(task) === true ? task : "";
                var moduleName = isNonEmptyString(module) === true ? module : "";
                var symbolName = isNonEmptyString(symbol) === true ? symbol : "";
                var dataType = null;
                var symbolType = null;
                var dataTypeURL = null;
                var symbolValue = null;
                var dimensions = null;
                var scope = null;
                var parsedType = null;
                var isSharedModule = taskName === SHARED_TAG && moduleName === SHARED_TAG;
                var symbolTitle = isSharedModule === true ? `RAPID/${symbolName}` : `RAPID/${taskName}/${moduleName}/${symbolName}`;
                var hasValidSetup = function() {
                    if (taskName === null || moduleName === null || symbolName === null) return false;
                    if (taskName === "" || moduleName === "" || symbolName === "") return false;
                    return true;
                }();
                this.getTitle = function() {
                    return symbolTitle;
                };
                this.getProperties = function() {
                    return refreshProperties().then(() => {
                        var properties = {
                            taskName: taskName,
                            moduleName: moduleName,
                            symbolName: symbolName,
                            dataType: dataType,
                            symbolType: symbolType,
                            dimensions: dimensions,
                            scope: scope,
                            dataTypeURL: dataTypeURL
                        };
                        return Promise.resolve(properties);
                    }).catch(err => Promise.reject(err));
                };
                this.getName = function() {
                    return symbolName;
                };
                this.getModuleName = function() {
                    return moduleName;
                };
                this.getTaskName = function() {
                    return taskName;
                };
                this.getDataType = function() {
                    if (dataType !== null) return Promise.resolve(dataType);
                    return refreshProperties().then(() => Promise.resolve(dataType)).catch(err => Promise.reject(err));
                };
                this.getSymbolType = function() {
                    if (symbolType !== null) return Promise.resolve(symbolType);
                    return refreshProperties().then(() => Promise.resolve(symbolType)).catch(err => Promise.reject(err));
                };
                this.getDimensions = function() {
                    if (dimensions !== null) return Promise.resolve(dimensions);
                    return refreshProperties().then(() => Promise.resolve(dimensions)).catch(err => Promise.reject(err));
                };
                this.getScope = function() {
                    if (scope !== null) return Promise.resolve(scope);
                    return refreshProperties().then(() => Promise.resolve(scope)).catch(err => Promise.reject(err));
                };
                this.getTypeURL = function() {
                    if (dataTypeURL !== null) return Promise.resolve(dataTypeURL);
                    return refreshProperties().then(() => Promise.resolve(dataTypeURL)).catch(err => Promise.reject(err));
                };
                this.getValue = function() {
                    if (symbolValue !== null) {
                        if (parsedType === null) {
                            return RWS.RapidData.Type.getType(this).then(x => {
                                parsedType = x;
                                return RWS.RapidData.Value.parseRawValue(parsedType, symbolValue);
                            }).catch(err => Promise.reject(err));
                        }
                        return RWS.RapidData.Value.parseRawValue(parsedType, symbolValue);
                    }
                    return this.fetch().then(() => {
                        return RWS.RapidData.Type.getType(this).then(x => {
                            parsedType = x;
                            return RWS.RapidData.Value.parseRawValue(parsedType, symbolValue);
                        }).catch(err => Promise.reject(err));
                    }).catch(err => Promise.reject(err));
                };
                const getArrayType = (base, indexes) => {
                    if (base.isArray === false) throw new Error(`Type '${base.type}' is not an array.`);
                    if (indexes.length > base.dimensions.length) throw new Error("More indexes provided than array contains dimensions.");
                    let ret = JSON.parse(JSON.stringify(base));
                    for (let iii = 0; iii < indexes.length; iii++) {
                        ret.dimensions.shift();
                    }
                    if (ret.dimensions.length <= 0) ret.isArray = false;
                    ret.url = dataTypeURL;
                    return ret;
                };
                this.getArrayItem = async function(...indexes) {
                    if (dimensions === null || dimensions.length <= 0) return rejectWithStatus("Get array item failed. >>> Cannot access data as array.");
                    if (indexes.length > dimensions.length) return rejectWithStatus("Get array item failed. >>> More indexes provided than array contains dimensions.");
                    for (let iii = 0; iii < indexes.length; iii++) {
                        if (typeof indexes[iii] !== "number" || dimensions[iii] < indexes[iii] || indexes[iii] < 1) return rejectWithStatus("Get array item failed. >>> Index out of bounds.");
                    }
                    if (parsedType === null) {
                        parsedType = await RWS.RapidData.Type.getType(this);
                    }
                    let arrayType = null;
                    try {
                        arrayType = getArrayType(parsedType, indexes);
                    } catch (error) {
                        return rejectWithStatus("Failed to get array item.", error);
                    }
                    return fetchItem(indexes).then(x => RWS.RapidData.Value.parseRawValue(arrayType, x)).catch(err => rejectWithStatus("Error fetching value.", err));
                };
                this.getRecordItem = function(...components) {
                    let indexes = [];
                    let type = null;
                    return getParsedType(this).then(x1 => getRecordIndexes(x1, components, indexes)).then(x2 => {
                        type = x2.type;
                        return fetchItem(x2.indexes);
                    }).then(x3 => RWS.RapidData.Value.parseRawValue(type, x3)).catch(err => rejectWithStatus("Get record item failed.", err));
                };
                this.getRawValue = function() {
                    if (symbolValue !== null) {
                        return Promise.resolve(symbolValue);
                    }
                    return this.fetch().then(() => Promise.resolve(symbolValue)).catch(err => Promise.reject(err));
                };
                this.setValue = value => {
                    if (hasValidSetup === false) return Promise.reject(`Symbol path '${getSymbolUrl()}' not valid.`);
                    let url = getSymbolUrl() + "/data";
                    let sVal = RWS.RapidData.String.stringify(value);
                    let hasMastership = false;
                    let error = null;
                    return requestMastership().then(() => {
                        hasMastership = true;
                        return o.Network.post(url, "value=" + encodeURIComponent(sVal));
                    }).catch(err => {
                        if (hasMastership === true) {
                            error = err;
                            return Promise.resolve();
                        }
                        return rejectWithStatus("Failed to get Mastership.", err);
                    }).then(() => releaseMastership()).then(() => {
                        if (error !== null) return rejectWithStatus("Failed to set value.", error);
                        return Promise.resolve();
                    });
                };
                this.setRawValue = (value, ...indexes) => {
                    if (hasValidSetup === false) return rejectWithStatus(`Symbol path '${getSymbolUrl()}' not valid.`);
                    let sInd = "";
                    if (indexes !== null && Array.isArray(indexes) && indexes.length > 0) {
                        sInd = "{";
                        for (let iii = 0; iii < indexes.length; iii++) {
                            sInd += indexes[iii].toString();
                            if (iii < indexes.length - 1) sInd += ",";
                        }
                        sInd += "}";
                    }
                    let url = getSymbolUrl() + encodeURIComponent(sInd) + "/data";
                    let hasMastership = false;
                    let error = null;
                    return requestMastership().then(() => {
                        hasMastership = true;
                        return o.Network.post(url, "value=" + encodeURIComponent(value));
                    }).catch(err => {
                        if (hasMastership === true) {
                            error = err;
                            return Promise.resolve();
                        }
                        return rejectWithStatus("Failed to get Mastership.", err);
                    }).then(() => releaseMastership()).then(() => {
                        if (error !== null) return rejectWithStatus("Failed to set raw value.", error);
                        return Promise.resolve();
                    });
                };
                this.setArrayItem = function(value, ...indexes) {
                    if (dimensions === null || dimensions.length <= 0) return rejectWithStatus("Set array item failed. >>> Cannot access data as array.");
                    if (indexes.length > dimensions.length) return rejectWithStatus("Set array item failed. >>> More indexes provided than array contains dimensions.");
                    for (let iii = 0; iii < indexes.length; iii++) {
                        if (typeof indexes[iii] !== "number" || dimensions[iii] < indexes[iii] || indexes[iii] < 1) return rejectWithStatus("Set array item failed. >>> Index out of bounds.");
                    }
                    let sVal = RWS.RapidData.String.stringify(value);
                    return setItem(indexes, sVal);
                };
                this.setRecordItem = function(value, ...components) {
                    let indexes = [];
                    return getParsedType(this).then(x1 => getRecordIndexes(x1, components, indexes)).then(() => {
                        let sVal = RWS.RapidData.String.stringify(value);
                        return setItem(indexes, sVal);
                    }).catch(err => rejectWithStatus("Set record item failed.", err));
                };
                this.fetch = function() {
                    if (hasValidSetup === false) return rejectWithStatus(`Symbol path '${getSymbolUrl()}' not valid.`);
                    const processData = json => {
                        for (const item of json.state) {
                            if (item._type === "rap-data") {
                                symbolValue = item.value;
                                break;
                            }
                        }
                    };
                    let url = getSymbolUrl() + "/data";
                    return o.Network.get(url).then(res => {
                        let json = parseJSON(res.responseText);
                        if (json === undefined) return reject("Could not parse JSON..");
                        return verifyReturnCode(json).then(() => {
                            processData(json);
                            return Promise.resolve("Fetched Data!");
                        }).catch(errors => {
                            if (errors.hasOwnProperty("pgmname_ret")) {
                                let err = errors["pgmname_ret"];
                                if (err.hasOwnProperty("code") === false || err.code !== "-1073445865") {
                                    return Promise.reject(err);
                                }
                                if (dimensions.length > 0) {
                                    return fetchByItem();
                                }
                                return Promise.reject("Data is too large to retrieve.");
                            }
                            processData(json);
                            return Promise.resolve("Fetched Data!");
                        });
                    }).catch(err => rejectWithStatus("Error fetching Rapid data value.", err));
                };
                const getParsedType = function(data) {
                    if (parsedType !== null && typeof parsedType !== "undefined") return Promise.resolve(parsedType);
                    return RWS.RapidData.Type.getType(data).then(x => {
                        parsedType = x;
                        return Promise.resolve(x);
                    }).catch(err => Promise.reject(err));
                };
                const getRecordIndexes = function(rdType, components, indexes = []) {
                    let component = "";
                    try {
                        if (components.length <= 0) return Promise.resolve({
                            type: rdType,
                            indexes: indexes
                        });
                        if (rdType.isRecord === false) return Promise.reject(`Get record indexes failed. >>> Data type '${rdType.url}' is not a Record.`);
                        component = components.shift();
                        for (let iii = 0; iii < rdType.components.length; iii++) {
                            if (rdType.components[iii].name === component) {
                                indexes.push(iii + 1);
                                let t = RWS.getCachedSymbolType(rdType.components[iii].type.url);
                                if (typeof t === "undefined") return Promise.reject(`Get record indexes failed. >>> Component '${component}' not found in Record '${rdType.type}'.`);
                                return getRecordIndexes(t, components, indexes);
                            }
                        }
                    } catch (error) {
                        o.writeDebug(`Get record indexes failed.\n${error}'`, 3);
                        return Promise.reject(`Get record indexes failed. >>> ${error}'`);
                    }
                    return Promise.reject(`Get record indexes failed. >>> Component '${component}' not found in Record '${rdType.type}'.`);
                };
                const fetchItem = function(indexes) {
                    return new Promise((resolve, reject) => {
                        let s = "{";
                        for (let iii = 0; iii < indexes.length; iii++) {
                            s += indexes[iii];
                            if (iii < indexes.length - 1) s += ",";
                        }
                        s += "}";
                        let url = `${getSymbolUrl()}${encodeURIComponent(s)}/data`;
                        return o.Network.get(url).then(res => {
                            let obj = parseJSON(res.responseText);
                            if (obj === undefined) return Promise.reject("Could not parse JSON.");
                            for (const item of obj.state) {
                                if (item._type === "rap-data") {
                                    return resolve(item.value);
                                }
                            }
                            reject(createStatusObject(`Data not found when fetching Rapid data item with index = ${indexes.toString()}.`));
                        }).catch(err => reject(createStatusObject(`Error fetching Rapid data item with index = ${indexes.toString()}.`, err)));
                    });
                };
                const setItem = function(indexes, value) {
                    let url = null;
                    let body = null;
                    try {
                        let s = "{";
                        for (let iii = 0; iii < indexes.length; iii++) {
                            s += indexes[iii];
                            if (iii < indexes.length - 1) s += ",";
                        }
                        s += "}";
                        url = `${getSymbolUrl()}${encodeURIComponent(s)}/data`;
                        body = `value=${encodeURIComponent(value)}`;
                    } catch (error) {
                        let s = `Failed to set item value. >>> ${error}`;
                        o.writeDebug(s);
                        return rejectWithStatus(s);
                    }
                    return o.Mastership.request().then(() => {
                        return o.Network.post(url, body).then(() => {
                            return o.Mastership.release().then(() => Promise.resolve("Value set!")).catch(err => Promise.reject("Item value set but failed to release mastership. >>> " + err));
                        }).catch(err => {
                            let handled = false;
                            let error = JSON.stringify(err);
                            return o.Mastership.release().then(() => {
                                handled = true;
                                return Promise.reject("Failed to set item value. >>> " + error);
                            }).catch(err2 => {
                                if (handled === true) {
                                    return Promise.reject(err2);
                                } else {
                                    return Promise.reject("Failed to set item value. >>> " + error + " >>> Failed to release mastership. >>> " + JSON.stringify(err2));
                                }
                            });
                        });
                    }).catch(err => rejectWithStatus("setItem failed.", err));
                };
                const fetchByItem = function() {
                    return new Promise((resolve, reject) => {
                        let s = "[";
                        let parts = [];
                        for (let iii = 1; iii <= dimensions[0]; iii++) {
                            let url = `${getSymbolUrl()}{${iii.toString()}}/data`;
                            parts.push(() => new Promise((resolve, reject) => {
                                o.Network.get(url).then(res => {
                                    let obj = parseJSON(res.responseText);
                                    if (obj === undefined) return Promise.reject("Could not parse JSON.");
                                    for (const item of obj.state) {
                                        if (item._type === "rap-data") {
                                            s += item.value + ",";
                                            break;
                                        }
                                    }
                                    return resolve();
                                }).catch(err => reject(`Error fetching Rapid data value >>> ${err}`));
                            }));
                        }
                        return parts.reduce((partChain, currentPart) => partChain.then(currentPart), Promise.resolve()).then(() => {
                            symbolValue = s.slice(0, -1) + "]";
                            resolve("Fetched Data!");
                        }).catch(err => reject(err));
                    });
                };
                var refreshProperties = function() {
                    if (hasValidSetup === false) return Promise.reject(`Symbol path '${getSymbolUrl()}' not valid.`);
                    let url = getSymbolUrl() + "/properties";
                    return o.Network.get(url).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (obj === undefined) return Promise.reject("Could not parse JSON.");
                        for (const item of obj._embedded.resources) {
                            if (item._type === "rap-symproppers" || item._type === "rap-sympropvar" || item._type === "rap-sympropconstant") {
                                if (item.symtyp === "per") symbolType = "persistent"; else if (item.symtyp === "con") symbolType = "constant"; else if (item.symtyp === "var") symbolType = "variable"; else symbolType = item.symtyp;
                                if (item.hasOwnProperty("local") && item.local.toLowerCase() === "true") scope = "local"; else if (symbolType === "persistent" && item.hasOwnProperty("taskpers") && item.taskpers.toLowerCase() === "true") scope = "task"; else if (symbolType === "variable" && item.hasOwnProperty("taskvar") && item.taskvar.toLowerCase() === "true") scope = "task"; else scope = "global";
                                dataType = item.dattyp;
                                dataTypeURL = item.typurl;
                                dimensions = [];
                                if (isNonEmptyString(item.dim.trim()) === true) {
                                    let splits = item.dim.trim().split(" ");
                                    for (const s of splits) {
                                        dimensions.push(parseInt(s));
                                    }
                                }
                                break;
                            }
                        }
                        if (dataType === null || dataTypeURL === null) {
                            return Promise.reject("Could not find symbol's data value in RWS response.");
                        }
                        return Promise.resolve();
                    }).catch(err => rejectWithStatus("Failed getting properties.", err));
                };
                var callbacks = [];
                this.addCallbackOnChanged = function(callback) {
                    if (typeof callback !== "function") throw new Error("callback is not a valid function");
                    callbacks.push(callback);
                };
                this.onchanged = async newValue => {
                    if (newValue !== null && typeof newValue === "object" && typeof newValue.value === "string" && newValue.value.trim().length > 0) {
                        symbolValue = newValue.value;
                    } else {
                        try {
                            await this.fetch();
                        } catch (error) {
                            o.writeDebug(`Failed to get value for '${this.getTitle()}'. >>> ${error}`);
                        }
                    }
                    for (let iii = 0; iii < callbacks.length; iii++) {
                        try {
                            callbacks[iii](symbolValue);
                        } catch (error) {
                            o.writeDebug(`Rapid.Data callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                this.getResourceString = function() {
                    return getSymbolUrl() + "/data;value";
                };
                const raiseEvent = async () => {
                    this.onchanged(null);
                };
                this.subscribe = function(raiseInitial = false) {
                    if (raiseInitial === true) return o.Subscriptions.subscribe([ this ], raiseEvent);
                    return o.Subscriptions.subscribe([ this ]);
                };
                this.unsubscribe = function() {
                    return o.Subscriptions.unsubscribe([ this ]);
                };
                function getSymbolUrl() {
                    let url = "/rw/rapid/symbol/RAPID/";
                    url += isSharedModule === true ? encodeURIComponent(symbolName) : `${encodeURIComponent(taskName)}/${encodeURIComponent(moduleName)}/${encodeURIComponent(symbolName)}`;
                    return url;
                }
            }
            function parsePointers(obj) {
                let pcp = {};
                pcp.programPointer = {};
                pcp.motionPointer = {};
                for (const item of obj.state) {
                    if (item._type === "pcp-info" && item._title === "progpointer") {
                        pcp.programPointer["moduleName"] = item.hasOwnProperty("modulemame") ? item.modulemame : "";
                        pcp.programPointer["routineName"] = item.hasOwnProperty("routinename") ? item.routinename : "";
                        pcp.programPointer["beginPosition"] = item.hasOwnProperty("beginposition") ? item.beginposition : "";
                        pcp.programPointer["endPosition"] = item.hasOwnProperty("endposition") ? item.endposition : "";
                        pcp.programPointer["hasValue"] = pcp.programPointer["moduleName"] !== "" || pcp.programPointer["routineName"] !== "" || pcp.programPointer["beginPosition"] !== "" || pcp.programPointer["endPosition"] !== "";
                    }
                    if (item._type === "pcp-info" && item._title === "motionpointer") {
                        pcp.motionPointer["moduleName"] = item.hasOwnProperty("modulename") ? item.modulename : "";
                        pcp.motionPointer["routineName"] = item.hasOwnProperty("routinename") ? item.routinename : "";
                        pcp.motionPointer["beginPosition"] = item.hasOwnProperty("begposition") ? item.begposition : "";
                        pcp.motionPointer["endPosition"] = item.hasOwnProperty("endposition") ? item.endposition : "";
                        pcp.motionPointer["hasValue"] = pcp.motionPointer["moduleName"] !== "" || pcp.motionPointer["routineName"] !== "" || pcp.motionPointer["beginPosition"] !== "" || pcp.motionPointer["endPosition"] !== "";
                    }
                }
                return pcp;
            }
            this.getTasks = function() {
                return o.Network.get("/rw/rapid/tasks").then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    let tasks = [];
                    for (const item of obj._embedded.resources) {
                        if (item._type === "rap-task-li") {
                            tasks.push(new Task(item.name));
                        }
                    }
                    return Promise.resolve(tasks);
                }).catch(err => rejectWithStatus("Error getting task list.", err));
            };
            this.getTask = function(taskName) {
                let task = new Task(taskName);
                return task.getProperties().then(() => Promise.resolve(task)).catch(err => Promise.reject(err));
            };
            this.getProgramInfo = function(taskName) {
                return new Task(taskName).getProgramInfo();
            };
            this.getModuleNames = function(taskName) {
                return new Task(taskName).getModuleNames();
            };
            this.getModule = function(taskName, moduleName) {
                let mod = new Module(taskName, moduleName);
                return mod.getProperties().then(() => Promise.resolve(mod)).catch(err => Promise.reject(err));
            };
            this.getData = function(taskName, moduleName, symbolName) {
                let data = new Data(taskName, moduleName, symbolName);
                return data.getProperties().then(() => Promise.resolve(data)).catch(err => Promise.reject(err));
            };
            this.setDataValue = function(taskName, moduleName, symbolName, value, ...indexes) {
                return new Data(taskName, moduleName, symbolName).setRawValue(value, ...indexes);
            };
            this.getSharedData = function(symbolName) {
                let data = new Data(SHARED_TAG, SHARED_TAG, symbolName);
                return data.getProperties().then(() => Promise.resolve(data)).catch(err => Promise.reject(err));
            };
            this.setSharedDataValue = function(symbolName, value) {
                return new Data(SHARED_TAG, SHARED_TAG, symbolName).setRawValue(value);
            };
            this.getExecutionState = () => {
                return o.Network.get("/rw/rapid/execution").then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    let mode = null;
                    for (const item of obj.state) {
                        if (item._type === "rap-execution") {
                            mode = item.ctrlexecstate;
                            break;
                        }
                    }
                    if (mode === null) {
                        return Promise.reject("Could not find the execution state in RWS response");
                    }
                    return Promise.resolve(mode);
                }).catch(err => rejectWithStatus("Could not get the execution state.", err));
            };
            this.startExecution = ({
                regainMode = "continue",
                executionMode = "continue",
                cycleMode = "forever",
                condition = "none",
                stopAtBreakpoint = true,
                enableByTSP = true
            } = {}) => {
                const validRegainModes = {
                    continue: "continue",
                    regain: "regain",
                    clear: "clear",
                    enter_consume: "enterconsume"
                };
                const validExecutionModes = {
                    continue: "continue",
                    step_in: "stepin",
                    step_over: "stepover",
                    step_out: "stepout",
                    step_backwards: "stepback",
                    step_to_last: "steplast",
                    step_to_motion: "stepmotion"
                };
                const validCycleModes = {
                    forever: "forever",
                    as_is: "asis",
                    once: "once"
                };
                const validConditions = {
                    none: "none",
                    call_chain: "callchain"
                };
                if (validRegainModes.hasOwnProperty(regainMode) === false) rejectWithStatus("Illegal parameter 'regainMode'");
                if (validExecutionModes.hasOwnProperty(executionMode) === false) rejectWithStatus("Illegal parameter 'executionMode'");
                if (validCycleModes.hasOwnProperty(cycleMode) === false) rejectWithStatus("Illegal parameter 'cycleMode'");
                if (validConditions.hasOwnProperty(condition) === false) rejectWithStatus("Illegal parameter 'condition'");
                let body = "";
                body += "regain=" + encodeURIComponent(validRegainModes[regainMode]);
                body += "&execmode=" + encodeURIComponent(validExecutionModes[executionMode]);
                body += "&cycle=" + encodeURIComponent(validCycleModes[cycleMode]);
                body += "&condition=" + encodeURIComponent(validConditions[condition]);
                if (stopAtBreakpoint === true) body += "&stopatbp=enabled"; else body += "&stopatbp=disabled";
                if (enableByTSP === true) body += "&alltaskbytsp=true"; else body += "&alltaskbytsp=false";
                return o.Network.post("/rw/rapid/execution/start", body).then(() => Promise.resolve()).catch(err => rejectWithStatus("Could not start execution.", err));
            };
            this.stopExecution = ({
                stopMode = "stop",
                useTSP = "normal"
            } = {}) => {
                const validStopModes = {
                    cycle: "cycle",
                    instruction: "instr",
                    stop: "stop",
                    quick_stop: "qstop"
                };
                const validUseTSPOptions = {
                    normal: "normal",
                    all_tasks: "alltask"
                };
                if (validStopModes.hasOwnProperty(stopMode) === false) rejectWithStatus("Illegal parameter 'stopMode'");
                if (validUseTSPOptions.hasOwnProperty(useTSP) === false) rejectWithStatus("Illegal parameter 'useTSP'");
                let body = "";
                body += "stopmode=" + encodeURIComponent(validStopModes[stopMode]);
                body += "&usetsp=" + encodeURIComponent(validUseTSPOptions[useTSP]);
                return o.Network.post("/rw/rapid/execution/stop", body).then(() => Promise.resolve()).catch(err => rejectWithStatus("Could not stop execution.", err));
            };
            this.resetPP = () => {
                let body = "";
                let hasMastership = false;
                let error = null;
                return requestMastership().then(() => {
                    hasMastership = true;
                    return o.Network.post("/rw/rapid/execution/resetpp", body);
                }).catch(err => {
                    if (hasMastership === true) {
                        error = err;
                        return Promise.resolve();
                    }
                    return rejectWithStatus("Failed to get Mastership.", err);
                }).then(() => releaseMastership()).then(() => {
                    if (error !== null) return rejectWithStatus("Failed to reset PP.", error);
                    return Promise.resolve();
                });
            };
            this.getDefaultSearchProperties = () => {
                return {
                    isInstalled: false,
                    isShared: false,
                    method: this.SearchMethods.block,
                    searchURL: "RAPID",
                    types: this.SymbolTypes.any,
                    recursive: true,
                    skipShared: false,
                    isInUse: false
                };
            };
            this.searchSymbols = (properties = this.getDefaultSearchProperties(), dataType = "", regexp = "") => {
                const rwsSymbolType = {
                    con: "constant",
                    var: "variable",
                    per: "pers",
                    fun: "function",
                    prc: "procedure",
                    trp: "trap",
                    mod: "module",
                    tsk: "task"
                };
                const checkProperties = properties => {
                    let errors = [];
                    const validProperties = [ "isInstalled", "isShared", "method", "searchURL", "types", "recursive", "skipShared", "isInUse" ];
                    let keys = Object.keys(properties);
                    for (let iii = 0; iii < keys.length; iii++) {
                        if (validProperties.includes(keys[iii]) === false) errors.push(`Properties include unknown setting '${keys[iii]}'`);
                    }
                    if (properties.hasOwnProperty("isInstalled") !== true) {
                        errors.push("Search property 'isInstalled' is missing.");
                    } else {
                        if (typeof properties.isInstalled !== "boolean") errors.push("Search property 'isInstalled' is invalid.");
                    }
                    if (properties.hasOwnProperty("isShared") !== true) {
                        errors.push("Search property 'isShared' is missing.");
                    } else {
                        if (typeof properties.isShared !== "boolean") errors.push("Search property 'isShared' is invalid.");
                    }
                    if (properties.hasOwnProperty("method") !== true) {
                        errors.push("Search property 'method' is missing.");
                    } else {
                        if (properties.method !== this.SearchMethods.block && properties.method !== this.SearchMethods.scope) errors.push("Search property 'method' is invalid.");
                        if (properties.hasOwnProperty("searchURL") !== true) {
                            errors.push("Search property 'searchURL' is missing.");
                        } else {
                            if (typeof properties.searchURL !== "string") errors.push("Search property 'searchURL' is invalid.");
                        }
                    }
                    if (properties.hasOwnProperty("types") !== true) {
                        errors.push("Search property 'types' is missing.");
                    } else {
                        if (typeof properties.types !== "number") errors.push("Search property 'types' is invalid.");
                    }
                    if (properties.hasOwnProperty("recursive") !== true) {
                        errors.push("Search property 'recursive' is missing.");
                    } else {
                        if (typeof properties.recursive !== "boolean") errors.push("Search property 'recursive' is invalid.");
                    }
                    if (properties.hasOwnProperty("skipShared") !== true) {
                        errors.push("Search property 'skipShared' is missing.");
                    } else {
                        if (typeof properties.skipShared !== "boolean") errors.push("Search property 'skipShared' is invalid.");
                    }
                    if (properties.hasOwnProperty("isInUse") !== true) {
                        errors.push("Search property 'isInUse' is missing.");
                    } else {
                        if (typeof properties.isInUse !== "boolean") errors.push("Search property 'isInUse' is invalid.");
                    }
                    return errors;
                };
                const getBodyText = (properties, dataType, regexp) => {
                    let text = ``;
                    if ((properties.method & this.SearchMethods.scope) == this.SearchMethods.scope) text = `view=scope`; else if ((properties.method & this.SearchMethods.block) == this.SearchMethods.block) text = `view=block`;
                    text += `&blockurl=${encodeURIComponent(properties.searchURL)}`;
                    if ((properties.types & this.SymbolTypes.constant) == this.SymbolTypes.constant) text += `&symtyp=con`;
                    if ((properties.types & this.SymbolTypes.variable) == this.SymbolTypes.variable) text += `&symtyp=var`;
                    if ((properties.types & this.SymbolTypes.persistent) == this.SymbolTypes.persistent) text += `&symtyp=per`;
                    if ((properties.types & this.SymbolTypes.function) == this.SymbolTypes.function) text += `&symtyp=fun`;
                    if ((properties.types & this.SymbolTypes.procedure) == this.SymbolTypes.procedure) text += `&symtyp=prc`;
                    if ((properties.types & this.SymbolTypes.trap) == this.SymbolTypes.trap) text += `&symtyp=trp`;
                    if ((properties.types & this.SymbolTypes.module) == this.SymbolTypes.module) text += `&symtyp=mod`;
                    if ((properties.types & this.SymbolTypes.task) == this.SymbolTypes.task) text += `&symtyp=tsk`;
                    text += `&recursive=${properties.recursive.toString().toUpperCase()}`;
                    text += `&skipshared=${properties.skipShared.toString().toUpperCase()}`;
                    text += `&onlyused=${properties.isInUse.toString().toUpperCase()}`;
                    if (regexp !== "") text += `&regexp=${regexp}`;
                    if (dataType !== "") {
                        if (properties.isShared === true || properties.isInstalled === true) {
                            text += `&dattyp=${dataType}`;
                        } else {
                            let typurl = dataType.startsWith("/") ? dataType : `/${dataType}`;
                            typurl = typurl.toUpperCase().startsWith("/RAPID") ? typurl : encodeURIComponent(`RAPID${typurl}`);
                            text += `&typurl=${typurl}`;
                        }
                    }
                    return text;
                };
                const getSymbol = item => {
                    let symbol = {};
                    if (item.hasOwnProperty("name")) {
                        symbol["name"] = item["name"];
                    } else {
                        symbol["name"] = "";
                    }
                    if (item.hasOwnProperty("symburl")) {
                        symbol["scope"] = item["symburl"].split("/");
                    } else {
                        symbol["scope"] = [];
                    }
                    if (item.hasOwnProperty("symtyp")) {
                        if (rwsSymbolType.hasOwnProperty(item["symtyp"])) {
                            symbol["symbolType"] = rwsSymbolType[item["symtyp"]];
                        } else {
                            symbol["symbolType"] = "";
                        }
                    } else {
                        symbol["symbolType"] = "";
                    }
                    if (item.hasOwnProperty("dattyp")) {
                        symbol["dataType"] = item["dattyp"];
                    } else {
                        symbol["dataType"] = "";
                    }
                    return symbol;
                };
                const doSearch = (url, body, symbols) => {
                    if (url === "") return Promise.resolve(symbols);
                    return o.Network.post(url, body).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        if (obj._links.hasOwnProperty("next")) {
                            url = "/rw/rapid/" + obj._links["next"].href;
                        } else {
                            url = "";
                        }
                        for (const item of obj._embedded.resources) {
                            let sym = getSymbol(item);
                            symbols.push(sym);
                        }
                        return doSearch(url, body, symbols);
                    }).catch(err => Promise.reject(err));
                };
                let errList = checkProperties(properties);
                if (errList.length > 0) {
                    let s = errList.reduce((a, c) => a + "\n" + c, "").trim();
                    return rejectWithStatus("Indata contains errors.", s);
                }
                let body = getBodyText(properties, dataType, regexp);
                let symbols = [];
                let url = "/rw/rapid/symbols/search";
                return doSearch(url, body, symbols).then(() => Promise.resolve(symbols)).catch(err => rejectWithStatus("Failed to search symbols.", err));
            };
        }();
        o.IO = new function() {
            this.NetworkPhysicalState = {
                halted: "halted",
                running: "running",
                error: "error",
                startup: "startup",
                init: "init",
                unknown: "unknown"
            };
            this.NetworkLogicalState = {
                stopped: "stopped",
                started: "started",
                unknown: "unknown"
            };
            this.DevicePhysicalState = {
                deact: "deact",
                running: "running",
                error: "error",
                unconnect: "unconnect",
                unconfg: "unconfg",
                startup: "startup",
                init: "init",
                unknown: "unknown"
            };
            this.DeviceLogicalState = {
                disabled: "disabled",
                enabled: "enabled",
                unknown: "unknown"
            };
            this.SignalQuality = {
                bad: "bad",
                good: "good",
                unknown: "unknown"
            };
            this.SignalType = {
                DI: "DI",
                DO: "DO",
                AI: "AI",
                AO: "AO",
                GI: "GI",
                GO: "GO"
            };
            function Network(network) {
                var isUnassigned = network === UNASSIGNED_TAG;
                var networkPath = isUnassigned === true ? "" : `networks/${encodeURIComponent(network)}`;
                var networkName = isNonEmptyString(network) === true ? network : "";
                var physicalState = null;
                var logicalState = null;
                this.getName = function() {
                    return networkName;
                };
                this.getPhysicalState = function() {
                    if (physicalState !== null) return Promise.resolve(physicalState);
                    return this.fetch().then(() => Promise.resolve(physicalState)).catch(err => Promise.reject(err));
                };
                this.getLogicalState = function() {
                    if (logicalState !== null) return Promise.resolve(logicalState);
                    return this.fetch().then(() => Promise.resolve(logicalState)).catch(err => Promise.reject(err));
                };
                this.getDevice = function(deviceName) {
                    if (isUnassigned) return rejectWithStatus("Not allowed as Network is unassigned.");
                    return RWS.IO.getDevice(networkName, deviceName);
                };
                this.fetch = function() {
                    if (isUnassigned) return rejectWithStatus("Network is not valid, as it is unassigned.");
                    return o.Network.get(`/rw/iosystem/${networkPath}`).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        for (const item of obj._embedded.resources) {
                            if (item._type === "ios-network-li") {
                                physicalState = item.pstate;
                                logicalState = item.lstate;
                                break;
                            }
                        }
                        return Promise.resolve();
                    }).catch(err => rejectWithStatus("Failed updating network data.", err));
                };
            }
            this.createSignal_internal = (network, device, signal) => {
                return new Signal(network, device, signal);
            };
            function Device(network, device) {
                var isUnassigned = network === UNASSIGNED_TAG || device === UNASSIGNED_TAG;
                var devicePath = isUnassigned === true ? "" : `devices/${encodeURIComponent(network)}/${encodeURIComponent(device)}`;
                var networkName = isNonEmptyString(network) === true ? network : "";
                var deviceName = isNonEmptyString(device) === true ? device : "";
                var physicalState = null;
                var logicalState = null;
                this.getName = function() {
                    return deviceName;
                };
                this.getNetworkName = function() {
                    return networkName;
                };
                this.getNetwork = function() {
                    return RWS.IO.getNetwork(networkName);
                };
                this.getPhysicalState = function() {
                    if (physicalState !== null) return Promise.resolve(physicalState);
                    return this.fetch().then(() => Promise.resolve(physicalState)).catch(err => Promise.reject(err));
                };
                this.getLogicalState = function() {
                    if (logicalState !== null) return Promise.resolve(logicalState);
                    return this.fetch().then(() => Promise.resolve(logicalState)).catch(err => Promise.reject(err));
                };
                this.getSignal = function(signalName) {
                    let signal = RWS.IO.createSignal_internal(networkName, deviceName, signalName);
                    return signal.fetch().then(() => Promise.resolve(signal)).catch(err => Promise.reject(err));
                };
                this.fetch = function() {
                    if (isUnassigned) return rejectWithStatus("Device is not valid, as it is unassigned.");
                    return o.Network.get(`/rw/iosystem/${devicePath}`).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        for (const item of obj._embedded.resources) {
                            if (item._type === "ios-device-li") {
                                physicalState = item.pstate;
                                logicalState = item.lstate;
                                break;
                            }
                        }
                        return Promise.resolve();
                    }).catch(err => rejectWithStatus("Failed updating device data.", err));
                };
            }
            function Signal(network, device, signal, _category = null, _signalType = null, _signalValue = null, _isSimulated = null, _quality = null, _accessLvl = null, _writeAccess = null, _safeLvl = null) {
                let isUnassigned = network === UNASSIGNED_TAG && device === UNASSIGNED_TAG;
                let signalPath = isUnassigned === true ? `${encodeURIComponent(signal)}` : `${encodeURIComponent(network)}/${encodeURIComponent(device)}/${encodeURIComponent(signal)}`;
                let networkName = isNonEmptyString(network) === true ? network : "";
                let deviceName = isNonEmptyString(device) === true ? device : "";
                let signalName = isNonEmptyString(signal) === true ? signal : "";
                let category = _category;
                let signalType = _signalType;
                let signalValue = _signalValue;
                let isSimulated = _isSimulated;
                let quality = _quality;
                let accessLvl = _accessLvl;
                let writeAccess = _writeAccess;
                let safeLvl = _safeLvl;
                this.getPath = function() {
                    return signalPath;
                };
                this.getName = function() {
                    return signalName;
                };
                this.getNetworkName = function() {
                    return networkName;
                };
                this.getDeviceName = function() {
                    return deviceName;
                };
                this.getTitle = function() {
                    return signalName;
                };
                this.getIsSimulated = function() {
                    if (isSimulated !== null) return Promise.resolve(isSimulated);
                    return this.fetch().then(() => Promise.resolve(isSimulated)).catch(err => Promise.reject(err));
                };
                this.getQuality = function() {
                    if (quality !== null) return Promise.resolve(quality);
                    return this.fetch().then(() => Promise.resolve(quality)).catch(err => Promise.reject(err));
                };
                this.getCategory = function() {
                    if (category !== null) return Promise.resolve(category);
                    return this.fetch().then(() => Promise.resolve(category)).catch(err => Promise.reject(err));
                };
                this.getType = function() {
                    if (signalType !== null) return Promise.resolve(signalType);
                    return this.fetch().then(() => Promise.resolve(signalType)).catch(err => Promise.reject(err));
                };
                this.getAccessLevel = function() {
                    if (accessLvl !== null && accessLvl !== undefined) return Promise.resolve(accessLvl);
                    return this.fetch().then(() => Promise.resolve(accessLvl)).catch(err => Promise.reject(err));
                };
                this.getWriteAccess = function() {
                    if (writeAccess !== null && writeAccess !== undefined) return Promise.resolve(writeAccess);
                    return this.fetch().then(() => Promise.resolve(writeAccess)).catch(err => Promise.reject(err));
                };
                this.getSafeLevel = function() {
                    if (safeLvl !== null && safeLvl !== undefined) return Promise.resolve(safeLvl);
                    return this.fetch().then(() => Promise.resolve(safeLvl)).catch(err => Promise.reject(err));
                };
                this.getValue = function() {
                    if (signalValue !== null) return Promise.resolve(signalValue);
                    return this.fetch().then(() => Promise.resolve(signalValue)).catch(err => Promise.reject(err));
                };
                this.getDevice = function() {
                    if (isUnassigned) return rejectWithStatus("Not allowed as Signal is unassigned.");
                    return RWS.IO.getDevice(networkName, deviceName);
                };
                this.fetch = function() {
                    return o.Network.get(`/rw/iosystem/signals/${signalPath}`).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        for (const item of obj._embedded.resources) {
                            if (item._type === "ios-signal-li") {
                                signalType = item.type;
                                if (signalType === "AI" || signalType === "AO") {
                                    signalValue = parseFloat(item.lvalue);
                                } else {
                                    signalValue = parseInt(item.lvalue);
                                }
                                isSimulated = item.lstate === "simulated";
                                quality = item.quality;
                                category = item.category;
                                accessLvl = item["access-level"];
                                writeAccess = item["write-access"];
                                safeLvl = item["safe-level"];
                                break;
                            }
                        }
                        return Promise.resolve("Refreshed Signal.");
                    }).catch(err => rejectWithStatus("Failed refreshing data.", err));
                };
                this.setValue = value => {
                    let hasMastership = false;
                    let error = null;
                    return requestMastership().then(() => {
                        hasMastership = true;
                        return o.Network.post(`/rw/iosystem/signals/${signalPath}/set-value`, `lvalue=${encodeURIComponent(value)}`);
                    }).catch(err => {
                        if (hasMastership === true) {
                            error = err;
                            return Promise.resolve();
                        }
                        return rejectWithStatus("Failed to get Mastership.", err);
                    }).then(() => releaseMastership()).then(() => {
                        if (error !== null) return rejectWithStatus("Failed to set value.", error);
                        return Promise.resolve();
                    });
                };
                var callbacks = [];
                this.addCallbackOnChanged = function(callback) {
                    if (typeof callback !== "function") throw new Error("callback is not a valid function");
                    callbacks.push(callback);
                };
                this.onchanged = function(newValue) {
                    let lvalue = "";
                    if (newValue.hasOwnProperty("lvalue")) lvalue = newValue["lvalue"];
                    if (signalType === "AI" || signalType === "AO") signalValue = parseFloat(lvalue); else signalValue = parseInt(lvalue);
                    for (let iii = 0; iii < callbacks.length; iii++) {
                        try {
                            callbacks[iii](signalValue);
                        } catch (error) {
                            o.writeDebug(`IO.Signal callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                this.getResourceString = function() {
                    return `/rw/iosystem/signals/${encodePath(signalPath)};state`;
                };
                const raiseEvent = async () => {
                    try {
                        await this.fetch();
                    } catch (error) {
                        o.writeDebug(`IO.Signal fetch failed. >>> ${error.toString()}`, 3);
                    }
                    for (let iii = 0; iii < callbacks.length; iii++) {
                        try {
                            callbacks[iii](signalValue);
                        } catch (error) {
                            o.writeDebug(`IO.Signal callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                this.subscribe = function(raiseInitial = false) {
                    if (raiseInitial === true) return o.Subscriptions.subscribe([ this ], raiseEvent);
                    return o.Subscriptions.subscribe([ this ]);
                };
                this.unsubscribe = function() {
                    return o.Subscriptions.unsubscribe([ this ]);
                };
            }
            this.getSignal = function(signal) {
                return this.searchSignals({
                    name: signal
                }).then(x => {
                    if (x.length < 1) return rejectWithStatus("Error getting signal.", "Signal not found.");
                    let s = null;
                    const signalLower = signal.toLowerCase();
                    for (let iii = 0; iii < x.length; iii++) {
                        if (x[iii].getName().toLowerCase() === signalLower) {
                            s = x[iii];
                            break;
                        }
                    }
                    if (s === null) return rejectWithStatus("Error getting signal.", "Signal not found.");
                    return Promise.resolve(s);
                }).catch(err => Promise.reject(err));
            };
            this.setSignalValue = function(signal, value) {
                return this.getSignal(signal).then(x => x.setValue(value)).catch(err => rejectWithStatus("Error setting signal.", err));
            };
            this.searchSignals = async (filter = {}) => {
                async function _searchSignalsImpl(filter, offset = 0) {
                    const CHUNK_SIZE = 100;
                    let body = "";
                    const refObject = {
                        name: "",
                        device: "",
                        network: "",
                        category: "",
                        "category-pon": "",
                        type: "",
                        invert: true,
                        blocked: true
                    };
                    const s = verifyDataType(filter, refObject);
                    if (s !== "") {
                        throw createStatusObject("Failed searching signal.", s);
                    }
                    try {
                        Object.keys(filter).forEach(key => {
                            body += `${key}=${encodeURIComponent(filter[key])}&`;
                        });
                        body = body.slice(0, -1);
                    } catch (error) {
                        throw createStatusObject("Failed searching signal.", error);
                    }
                    const signals = [];
                    let obj;
                    try {
                        const rwsRes = await o.Network.post(`/rw/iosystem/signals/signal-search-ex?start=${encodeURIComponent(offset)}&limit=${encodeURIComponent(CHUNK_SIZE)}`, body, {
                            Accept: "application/hal+json;v=2.0"
                        });
                        obj = parseJSON(rwsRes.responseText);
                        if (typeof obj === "undefined") throw "Could not parse JSON.";
                        for (const item of obj._embedded.resources) {
                            if (item._type === "ios-signal-li") {
                                const path = item._title.split("/");
                                let networkName = UNASSIGNED_TAG;
                                let deviceName = UNASSIGNED_TAG;
                                let signalName = "";
                                if (path.length === 1) {
                                    signalName = path[0];
                                } else if (path.length === 3) {
                                    networkName = path[0];
                                    deviceName = path[1];
                                    signalName = path[2];
                                } else {
                                    console.error(`Invalid signal data: '${item._title}'`);
                                    continue;
                                }
                                let signalValue;
                                if (item.type === "AI" || item.type === "AO") {
                                    signalValue = parseFloat(item.lvalue);
                                } else {
                                    signalValue = parseInt(item.lvalue);
                                }
                                const signal = new Signal(networkName, deviceName, signalName, item.category, item.type, signalValue, item.lstate === "simulated", item.quality, item["access-level"], item["write-access"], item["safe-level"]);
                                signals.push(signal);
                            }
                        }
                    } catch (error) {
                        throw createStatusObject("Failed searching signal.", error);
                    }
                    if (obj !== undefined && obj._links !== undefined && obj._links.next !== undefined) {
                        for (const sig of await _searchSignalsImpl(filter, offset + CHUNK_SIZE)) {
                            signals.push(sig);
                        }
                    }
                    return signals;
                }
                return await _searchSignalsImpl(filter);
            };
            this.getNetwork = function(networkName) {
                let url = "/rw/iosystem/networks";
                let body = `name=${encodeURIComponent(networkName)}`;
                return o.Network.post(url, body).then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    for (const item of obj._embedded.resources) {
                        if (item._type !== "ios-network-li") continue;
                        if (item.name === networkName) {
                            let network = new Network(networkName);
                            return Promise.resolve(network);
                        }
                    }
                    return Promise.reject(`Network '${networkName}' not found.`);
                }).catch(err => rejectWithStatus("Failed to search networks.", err));
            };
            this.getDevice = function(networkName, deviceName) {
                let url = "/rw/iosystem/devices";
                let body = `network=${encodeURIComponent(networkName)}&name=${encodeURIComponent(deviceName)}`;
                return o.Network.post(url, body).then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    for (const item of obj._embedded.resources) {
                        if (item._type !== "ios-device-li") continue;
                        if (item.name === deviceName) {
                            let device = new Device(networkName, deviceName);
                            return Promise.resolve(device);
                        }
                    }
                    return Promise.reject(`Device '${deviceName}' not found on network '${networkName}'.`);
                }).catch(err => rejectWithStatus("Failed to search devices.", err));
            };
        }();
        o.CFG = new function() {
            this.LoadMode = {
                add: "add",
                replace: "replace",
                "add-with-reset": "add-with-reset"
            };
            function Domain(name) {
                var domainName = name;
                this.getName = function() {
                    return domainName;
                };
                this.getTypes = function() {
                    const processGet = (url, instances) => {
                        if (url === "") return Promise.resolve(instances);
                        return o.Network.get(url).then(res => {
                            let obj = parseJSON(res.responseText);
                            if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                            if (obj._links.hasOwnProperty("next")) {
                                url = "/rw/cfg/" + encodeURI(obj._links["next"].href);
                            } else {
                                url = "";
                            }
                            for (const item of obj._embedded.resources) {
                                if (item._type !== "cfg-dt-li") continue;
                                let i = new Type(this, item._title);
                                types.push(i);
                            }
                            return processGet(url, types);
                        }).catch(err => Promise.reject(err));
                    };
                    let types = [];
                    let url = "/rw/cfg/" + encodeURIComponent(domainName);
                    return processGet(url, types).then(() => Promise.resolve(types)).catch(err => rejectWithStatus("Failed to get types.", err));
                };
                this.getInstances = function(type) {
                    return new Type(this, type).getInstances();
                };
                this.getInstanceByName = function(type, name) {
                    return new Type(this, type).getInstanceByName(name);
                };
                this.getInstanceById = function(type, id) {
                    return new Type(this, type).getInstanceById(id);
                };
                this.createInstance = function(type, name = "") {
                    return new Type(this, type).createInstance(name);
                };
                this.updateAttributesByName = function(type, name, attributes) {
                    return new Type(this, type).updateAttributesByName(name, attributes);
                };
                this.updateAttributesById = function(type, id, attributes) {
                    return new Type(this, type).updateAttributesById(id, attributes);
                };
                this.deleteInstanceByName = function(type, name) {
                    return new Type(this, type).deleteInstanceByName(name);
                };
                this.deleteInstanceById = async function(type, id) {
                    return new Type(this, type).deleteInstanceById(id);
                };
                this.saveToFile = function(filePath) {
                    let path = `/fileservice/${filePath}`;
                    let body = `filepath=${encodeURIComponent(path)}`;
                    return o.Network.post("/rw/cfg/" + encodePath(domainName) + "/saveas", body).then(() => Promise.resolve()).catch(err => rejectWithStatus("Failed to save file.", err));
                };
            }
            function Type(domain, name) {
                var parent = domain;
                var domainName = parent.getName();
                var typeName = name;
                this.getName = function() {
                    return typeName;
                };
                this.getDomainName = function() {
                    return domainName;
                };
                this.getDomain = function() {
                    return parent;
                };
                this.getInstances = function() {
                    const getInstance = item => {
                        let id = item.instanceid;
                        let attributes = {};
                        let name = "";
                        for (var u = 0; u < item.attrib.length; u++) {
                            attributes[item.attrib[u]._title] = item.attrib[u].value;
                            if (typeof item.attrib[u]._title === "string" && item.attrib[u]._title.toLowerCase() === "name") name = item.attrib[u].value;
                        }
                        return new Instance(this, id, name, attributes);
                    };
                    const checkExists = (instances, instance) => {
                        for (const i of instances) {
                            if (i.getInstanceId() === instance.getInstanceId()) return true;
                        }
                        return false;
                    };
                    const processGet = (url, instances) => {
                        if (url === "") return Promise.resolve(instances);
                        return o.Network.get(url).then(res => {
                            let obj = parseJSON(res.responseText);
                            if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                            if (obj._links.hasOwnProperty("next")) {
                                let splits = obj._links["next"].href.split("?");
                                if (splits.length === 2) {
                                    url = "/rw/cfg/" + encodeURIComponent(domainName) + "/" + encodeURIComponent(typeName) + "/instances?" + splits[1];
                                } else {
                                    url = "";
                                }
                            } else {
                                url = "";
                            }
                            if (obj._embedded.resources.length === 0) url = "";
                            for (const item of obj._embedded.resources) {
                                if (item._type !== "cfg-dt-instance-li") continue;
                                let i = getInstance(item);
                                if (checkExists(instances, i) === false) instances.push(i);
                            }
                            return processGet(url, instances);
                        }).catch(err => Promise.reject(err));
                    };
                    let instances = [];
                    let url = "/rw/cfg/" + encodeURIComponent(domainName) + "/" + encodeURIComponent(typeName) + "/instances";
                    return processGet(url, instances).then(() => Promise.resolve(instances)).catch(err => rejectWithStatus("Failed to get instances.", err));
                };
                this.getInstanceByName = function(name) {
                    return o.Network.get("/rw/cfg/" + encodeURIComponent(domainName) + "/" + encodeURIComponent(typeName) + "/instances/" + encodeURIComponent(name)).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        let attributes = {};
                        let instanceName = "";
                        let instanceId = "";
                        for (const item of obj.state) {
                            if (item._type === "cfg-dt-instance") {
                                instanceId = item.instanceid;
                                for (var iii = 0; iii < item.attrib.length; iii++) {
                                    attributes[item.attrib[iii]._title] = item.attrib[iii].value;
                                    if (typeof item.attrib[iii]._title === "string" && item.attrib[iii]._title.toLowerCase() === "name") instanceName = item.attrib[iii].value;
                                }
                                break;
                            }
                        }
                        if (instanceName !== "") {
                            return Promise.resolve(new Instance(this, instanceId, instanceName, attributes));
                        } else {
                            return Promise.reject("Incorrect instance returned.");
                        }
                    }).catch(err => rejectWithStatus(`Could not get instance '${name}'.`, err));
                };
                this.getInstanceById = function(id) {
                    return o.Network.get("/rw/cfg/" + encodeURIComponent(domainName) + "/" + encodeURIComponent(typeName) + "/instances/" + encodeURIComponent(id)).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        let attributes = {};
                        let instanceName = "";
                        let instanceId = "";
                        for (const item of obj.state) {
                            if (item._type === "cfg-dt-instance") {
                                instanceId = item.instanceid;
                                for (var iii = 0; iii < item.attrib.length; iii++) {
                                    attributes[item.attrib[iii]._title] = item.attrib[iii].value;
                                    if (typeof item.attrib[iii]._title === "string" && item.attrib[iii]._title.toLowerCase() === "name") instanceName = item.attrib[iii].value;
                                }
                                break;
                            }
                        }
                        if (instanceId !== "") {
                            return Promise.resolve(new Instance(this, instanceId, instanceName, attributes));
                        } else {
                            return Promise.reject("Incorrect instance returned.");
                        }
                    }).catch(err => rejectWithStatus(`Could not get instance '${id}'.`, err));
                };
                this.createInstance = function(name = "") {
                    let body = "name=";
                    let uri = "/rw/cfg/" + encodeURIComponent(domainName) + "/" + encodeURIComponent(typeName) + "/instances/create-default";
                    if (typeof name === "string" && name !== "") {
                        body += encodeURIComponent(name);
                    }
                    return o.Network.post(uri, body).then(x1 => Promise.resolve(x1)).catch(err => rejectWithStatus("Failed to create instance.", err));
                };
                this.updateAttributesByName = function(name, attributes) {
                    return this.getInstanceByName(name).then(instance => {
                        let inst = instance.updateAttributes(attributes);
                        return Promise.resolve(inst);
                    }).catch(err => rejectWithStatus("Could not update attributes.", err));
                };
                this.updateAttributesById = function(id, attributes) {
                    return this.getInstanceById(id).then(instance => {
                        let inst = instance.updateAttributes(attributes);
                        return Promise.resolve(inst);
                    }).catch(err => rejectWithStatus("Could not update attributes.", err));
                };
                this.deleteInstanceByName = async function(name) {
                    try {
                        let instance = await this.getInstanceByName(name);
                        return await instance.delete();
                    } catch (e) {
                        throw createStatusObject("Could not delete instance.", e);
                    }
                };
                this.deleteInstanceById = async function(id) {
                    try {
                        let instance = await this.getInstanceById(id);
                        return await instance.delete();
                    } catch (e) {
                        throw createStatusObject("Could not delete instance.", e);
                    }
                };
            }
            function Instance(type, id, name, attributes) {
                var parent = type;
                var instanceId = id;
                var instanceName = name;
                var domainName = parent.getDomainName();
                var typeName = parent.getName();
                var instanceAttributes = attributes;
                this.getInstanceId = function() {
                    return instanceId;
                };
                this.getInstanceName = function() {
                    return instanceName;
                };
                this.getTypeName = function() {
                    return typeName;
                };
                this.getType = function() {
                    return parent;
                };
                this.getAttributes = function() {
                    return instanceAttributes;
                };
                this.updateAttributes = function(attributes) {
                    var body = "";
                    for (let item in attributes) {
                        body += item + "=" + encodeURIComponent("[" + attributes[item] + ",1]") + "&";
                    }
                    body = body.replace(/&$/g, "");
                    var uri = "/rw/cfg/" + encodeURIComponent(domainName) + "/" + encodeURIComponent(typeName) + "/instances/" + encodeURIComponent(instanceId);
                    return o.Network.post(uri, body).then(() => {
                        try {
                            for (let item in attributes) {
                                if (instanceAttributes[item] !== undefined) {
                                    instanceAttributes[item] = attributes[item];
                                } else {
                                    let s = instanceName == "" ? instanceId : instanceName;
                                    o.writeDebug("attribute '" + item + "' does not exist on instance '" + s + "'");
                                }
                            }
                        } catch (error) {
                            o.writeDebug("Failed updating Instance object.");
                        }
                        return Promise.resolve();
                    }).catch(err => rejectWithStatus("Failed updating attributes.", err));
                };
                this.delete = async function() {
                    try {
                        const uri = `/rw/cfg/${encodeURIComponent(domainName)}/${encodeURIComponent(typeName)}/instances/${encodeURIComponent(instanceName == "" ? instanceId : instanceName)}`;
                        await o.Network.delete(uri);
                    } catch (e) {
                        throw createStatusObject("Error when deleting CFG instance.", e);
                    }
                };
            }
            this.getDomains = function() {
                return o.Network.get("/rw/cfg").then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    let domains = [];
                    for (const item of obj._embedded.resources) {
                        if (item._type === "cfg-domain-li") {
                            domains.push(new Domain(item._title));
                        }
                    }
                    if (domains.length == 0) {
                        return Promise.reject("Could not find any domains in RWS response");
                    }
                    return Promise.resolve(domains);
                }).catch(err => rejectWithStatus("Failed getting domains.", err));
            };
            this.saveConfiguration = function(domain, filePath) {
                return new Domain(domain).saveToFile(filePath);
            };
            this.verifyConfigurationFile = function(filePath, action = "add") {
                if (isNonEmptyString(filePath) === false) return rejectWithStatus("Invalid parameter 'filePath'.");
                if (typeof action === "string") action = action.toLowerCase();
                if (action !== "add" && action !== "replace" && action !== "add-with-reset") return rejectWithStatus("Invalid parameter 'action'.");
                let body = `filepath=${encodeURIComponent(filePath)}&action-type=${encodeURIComponent(action)}`;
                return o.Network.post("/rw/cfg/validate", body).then(() => Promise.resolve()).catch(err => rejectWithStatus(`Failed to verify the file '${filePath}'.`, err));
            };
            this.loadConfiguration = function(filePath, action = "add") {
                if (isNonEmptyString(filePath) === false) return rejectWithStatus("Invalid parameter 'filePath'.");
                if (typeof action === "string") action = action.toLowerCase();
                if (action !== "add" && action !== "replace" && action !== "add-with-reset") return rejectWithStatus("Invalid parameter 'action'.");
                let body = `filepath=${encodeURIComponent(filePath)}&action-type=${encodeURIComponent(action)}`;
                return o.Network.post("/rw/cfg/load", body).then(res => {
                    let location = res.getResponseHeader("Location");
                    if (location !== null) {
                        return waitProgressCompletion(location, COMMON_TIMEOUT).then(code => getStatusCode(code)).then(status => {
                            if (status.severity.toLowerCase() === "error") return Promise.reject({
                                message: "Progress resource reported error.",
                                controllerStatus: status
                            });
                            return Promise.resolve();
                        }).catch(err => Promise.reject(err));
                    }
                    o.writeDebug("loadConfiguration: Failed to get the location of progress resource. The file will be loaded but the call returns before it has completed.", 2);
                    return Promise.resolve();
                }).catch(err => rejectWithStatus(`Failed to load the file '${filePath}'.`, err));
            };
            this.getTypes = function(domain) {
                return new Domain(domain).getTypes();
            };
            this.getInstances = function(domain, type) {
                return new Domain(domain).getInstances(type);
            };
            this.getInstanceByName = function(domain, type, name) {
                return new Domain(domain).getInstanceByName(type, name);
            };
            this.getInstanceById = function(domain, type, id) {
                return new Domain(domain).getInstanceById(type, id);
            };
            this.createInstance = function(domain, type, name = "") {
                return new Domain(domain).createInstance(type, name);
            };
            this.updateAttributesByName = function(domain, type, name, attributes) {
                return new Domain(domain).updateAttributesByName(type, name, attributes);
            };
            this.updateAttributesById = function(domain, type, id, attributes) {
                return new Domain(domain).updateAttributesById(type, id, attributes);
            };
            this.deleteInstanceByName = function(domain, type, name) {
                return new Domain(domain).deleteInstanceByName(type, name);
            };
            this.deleteInstanceById = function(domain, type, id) {
                return new Domain(domain).deleteInstanceByName(type, id);
            };
        }();
        o.Controller = new function() {
            const replacables = {
                init: "initializing",
                motoron: "motors_on",
                motoroff: "motors_off",
                guardstop: "guard_stop",
                emergencystop: "emergency_stop",
                emergencystopreset: "emergency_stop_resetting",
                sysfail: "system_failure",
                INIT: "initializing",
                AUTO_CH: "automatic_changing",
                MANF_CH: "manual_full_changing",
                MANR: "manual_reduced",
                MANF: "manual_full",
                AUTO: "automatic",
                UNDEF: "undefined"
            };
            const processString = function(text) {
                if (typeof text !== "string" || text === null) return "";
                if (replacables.hasOwnProperty(text) === false) return text.toLowerCase();
                return replacables[text];
            };
            this.MonitorResources = {
                controllerState: "controller-state",
                operationMode: "operation-mode"
            };
            this.RestartModes = {
                restart: "restart",
                shutdown: "shutdown",
                bootApplication: "boot_application",
                resetSystem: "reset_system",
                resetRapid: "reset_rapid",
                revertToAutoSave: "revert_to_auto"
            };
            this.BackupIgnoreMismatches = {
                all: "all",
                systemId: "system-id",
                templateId: "template-id",
                none: "none"
            };
            this.BackupInclude = {
                all: "all",
                cfg: "cfg",
                modules: "modules"
            };
            this.ControllerStates = {
                initializing: "initializing",
                motors_on: "motors_on",
                motors_off: "motors_off",
                guard_stop: "guard_stop",
                emergency_stop: "emergency_stop",
                emergency_stop_resetting: "emergency_stop_resetting",
                system_failure: "system_failure"
            };
            this.MotorsState = {
                motors_on: "motors_on",
                motors_off: "motors_off"
            };
            this.OperationModes = {
                initializing: "initializing",
                automatic_changing: "automatic_changing",
                manual_full_changing: "manual_full_changing",
                manual_reduced: "manual_reduced",
                manual_full: "manual_full",
                automatic: "automatic",
                undefined: "undefined"
            };
            this.SettableOperationModes = {
                manual: "manual",
                manual_full: "manual_full",
                automatic: "automatic"
            };
            this.BackupStatus = {
                ok: "ok",
                system_id_mismatch: "system_id_mismatch",
                template_id_mismatch: "template_id_mismatch",
                file_or_directory_missing: "file_or_directory_missing",
                cfg_file_corrupt: "cfg_file_corrupt"
            };
            function Monitor(resource) {
                if (resource.toLowerCase() !== o.Controller.MonitorResources.controllerState && resource.toLowerCase() !== o.Controller.MonitorResources.operationMode) {
                    o.writeDebug("Unable to create Controller Monitor: Illegal resource.", 3);
                    return;
                }
                let resourceName = resource;
                const urls = {
                    "controller-state": "/rw/panel/ctrl-state",
                    "operation-mode": "/rw/panel/opmode"
                };
                const resourceStrings = {
                    "controller-state": "/rw/panel/ctrl-state",
                    "operation-mode": "/rw/panel/opmode"
                };
                var callbacks = [];
                this.getTitle = function() {
                    return urls[resourceName];
                };
                this.getResourceString = function() {
                    return resourceStrings[resourceName];
                };
                this.addCallbackOnChanged = function(callback) {
                    if (typeof callback !== "function") throw new Error("callback is not a valid function");
                    callbacks.push(callback);
                };
                this.onchanged = function(newValue) {
                    let parsedValue = {};
                    switch (resourceName) {
                      case "controller-state":
                        if (newValue.hasOwnProperty("ctrlstate")) parsedValue = processString(newValue["ctrlstate"]);
                        break;

                      case "operation-mode":
                        if (newValue.hasOwnProperty("opmode")) parsedValue = processString(newValue["opmode"]);
                        break;

                      default:
                        parsedValue = "";
                    }
                    for (let iii = 0; iii < callbacks.length; iii++) {
                        try {
                            callbacks[iii](parsedValue);
                        } catch (error) {
                            o.writeDebug(`Controller.Monitor callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                const raiseEvent = async () => {
                    const getValue = async () => {
                        let rawValue = await o.Network.get(urls[resourceName]).then(x1 => {
                            let obj = parseJSON(x1.responseText);
                            if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                            return obj;
                        }).catch(err => {
                            let s = JSON.stringify(err);
                            o.writeDebug(`Controller.raiseEvent failed getting value. >>> ${s}`);
                            return null;
                        });
                        if (rawValue === null) return null;
                        if (rawValue.hasOwnProperty("state") === false) return null;
                        let state = rawValue["state"][0];
                        let parsedValue = null;
                        switch (resourceName) {
                          case "controller-state":
                            if (state.hasOwnProperty("ctrlstate")) parsedValue = processString(state["ctrlstate"]);
                            break;

                          case "operation-mode":
                            if (state.hasOwnProperty("opmode")) parsedValue = processString(state["opmode"]);
                            break;

                          default:
                            o.writeDebug(`Unsupported resource '${resourceName}'`);
                        }
                        return parsedValue;
                    };
                    let value = await getValue();
                    if (value === null) return;
                    for (let iii = 0; iii < callbacks.length; iii++) {
                        try {
                            callbacks[iii](value);
                        } catch (error) {
                            o.writeDebug(`Controller.Monitor callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                this.subscribe = function(raiseInitial = false) {
                    if (raiseInitial === true) return o.Subscriptions.subscribe([ this ], raiseEvent);
                    return o.Subscriptions.subscribe([ this ]);
                };
                this.unsubscribe = function() {
                    return o.Subscriptions.unsubscribe([ this ]);
                };
            }
            this.getMonitor = function(resource) {
                return new Monitor(resource);
            };
            this.isVirtualController = async () => {
                return await o.isVirtualController();
            };
            this.getControllerState = () => {
                return o.Network.get("/rw/panel/ctrl-state").then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    let state = null;
                    for (const item of obj.state) {
                        if (item._type === "pnl-ctrlstate") {
                            state = processString(item.ctrlstate);
                            break;
                        }
                    }
                    if (state === null) {
                        return Promise.reject("Could not find the controller state in RWS response");
                    }
                    return Promise.resolve(state);
                }).catch(err => rejectWithStatus("Could not get controller state.", err));
            };
            this.setMotorsState = state => {
                let body = "ctrl-state=";
                if (typeof state === "string" && state.toLowerCase() === "motors_on") {
                    body += "motoron";
                } else if (typeof state === "string" && state.toLowerCase() == "motors_off") {
                    body += "motoroff";
                } else {
                    return rejectWithStatus("Unknown state.");
                }
                return o.Network.post("/rw/panel/ctrl-state", body).then(() => Promise.resolve()).catch(err => rejectWithStatus("Could not set motors state.", err));
            };
            this.getOperationMode = () => {
                return o.Network.get("/rw/panel/opmode").then(req => {
                    let obj = null;
                    try {
                        obj = JSON.parse(req.responseText);
                    } catch (error) {
                        return Promise.reject("Could not parse JSON.");
                    }
                    let mode = null;
                    for (const item of obj.state) {
                        if (item._type === "pnl-opmode") {
                            mode = processString(item.opmode);
                            break;
                        }
                    }
                    if (mode === null) {
                        return Promise.reject("Could not find the controller operation mode in RWS response");
                    }
                    return Promise.resolve(mode);
                }).catch(err => rejectWithStatus("Could not get controller operation mode.", err));
            };
            this.setOperationMode = mode => {
                if (typeof mode !== "string") return rejectWithStatus("Invalid parameter, 'mode' is not a string.");
                mode = mode.toLowerCase();
                let body = "";
                if (mode === "automatic") body = "opmode=auto"; else if (mode === "manual") body = "opmode=man"; else if (mode === "manual_full") body = "opmode=manf"; else return rejectWithStatus(`Invalid parameter mode='${mode}'.`);
                return o.Network.post("/rw/panel/opmode", body).then(() => Promise.resolve()).catch(err => rejectWithStatus("Could not set controller operation mode.", err));
            };
            this.restartController = async (mode = "restart") => {
                if (typeof mode !== "string") throw createStatusObject("Invalid parameter, 'mode' is not a string.");
                mode = mode.toLowerCase();
                let body = "";
                if (mode === "restart") body = "restart-mode=restart"; else if (mode === "shutdown") body = "restart-mode=shutdown"; else if (mode === "boot_application") body = "restart-mode=xstart"; else if (mode === "reset_system") body = "restart-mode=istart"; else if (mode === "reset_rapid") body = "restart-mode=pstart"; else if (mode === "revert_to_auto") body = "restart-mode=bstart"; else throw createStatusObject(`'@{mode}' is not a valid restart mode.`);
                const ERR_MSG = "Restart failed.";
                try {
                    await o.Mastership.request();
                } catch (e) {
                    throw createStatusObject(ERR_MSG, e);
                }
                try {
                    await o.Network.post("/ctrl/restart", body);
                } catch (e) {
                    throw createStatusObject(ERR_MSG, e);
                } finally {
                    try {
                        await o.Mastership.release();
                    } catch (e) {}
                }
            };
            this.getEnvironmentVariable = variable => {
                if (typeof variable !== "string") return rejectWithStatus("Illegal environment variable.");
                return o.Network.get(`/ctrl/${encodeURIComponent(variable)}`).then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    let value = "";
                    for (const item of obj.state) {
                        if (item._type === "ctrl-env") {
                            value = item["value"];
                            break;
                        }
                    }
                    if (value === "") return Promise.reject("value not found.");
                    return Promise.resolve(value);
                }).catch(err => rejectWithStatus(`Could not get environment variable '${variable}'.`, err));
            };
            this.getTime = () => {
                return o.Network.get("/ctrl/clock").then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    let datetime = "";
                    for (const item of obj.state) {
                        if (item._type === "ctrl-clock-info") {
                            datetime = item["datetime"];
                            break;
                        }
                    }
                    if (datetime === "") return Promise.reject("'datetime' not found.");
                    return Promise.resolve(datetime);
                }).catch(err => rejectWithStatus("Could not get time.", err));
            };
            this.getTimezone = async () => {
                try {
                    if (await o.isVirtualController() === true) {
                        throw createStatusObject(VC_NOT_SUPPORTED);
                    }
                    const res = await o.Network.get("/ctrl/clock/timezone");
                    const obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") {
                        throw "Could not parse JSON.";
                    }
                    let timezone = "";
                    for (const item of obj.state) {
                        if (item._type === "ctrl-timezone") {
                            timezone = item.timezone;
                            break;
                        }
                    }
                    if (timezone === "") {
                        throw "'ctrl-timezone' not found.";
                    }
                    return timezone;
                } catch (e) {
                    throw createStatusObject("Could not get timezone.", e);
                }
            };
            this.getIdentity = () => {
                return o.Network.get("/ctrl/identity").then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    let identity = "";
                    for (const item of obj.state) {
                        if (item._type === "ctrl-identity-info") {
                            identity = item["ctrl-name"];
                            break;
                        }
                    }
                    if (identity === "") return Promise.reject("'ctrl-name' not found.");
                    return Promise.resolve(identity);
                }).catch(err => rejectWithStatus("Could not get identity.", err));
            };
            this.getNetworkSettings = async () => {
                try {
                    if (await o.isVirtualController() === true) {
                        throw createStatusObject(VC_NOT_SUPPORTED);
                    }
                    const res = await o.Network.get("/ctrl/network");
                    const obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") {
                        throw "Could not parse JSON.";
                    }
                    const settingsList = [];
                    for (const item of obj.state) {
                        if (item._type === "ctrl-netw") {
                            let settings = {
                                id: item.title,
                                logicalName: item["logical-name"],
                                network: item["network"],
                                address: item["addr"],
                                mask: item["mask"],
                                primaryDNS: item["dns-primary"],
                                secondaryDNS: item["dns-secondary"],
                                DHCP: item["dhcp"].toLowerCase() === "true",
                                gateway: item["gateway"]
                            };
                            settingsList.push(settings);
                        }
                    }
                    return settingsList;
                } catch (err) {
                    throw createStatusObject("Could not get network settings.", err);
                }
            };
            this.getNetworkConnections = async () => {
                try {
                    if (await o.isVirtualController() === true) {
                        throw createStatusObject(VC_NOT_SUPPORTED);
                    }
                    const res = await o.Network.get("/ctrl/network/advanced");
                    const obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") {
                        throw "Could not parse JSON.";
                    }
                    const connectionsList = [];
                    for (const item of obj.state) {
                        if (item._type === "ctrl-netw-adv") {
                            let connection = {
                                id: item.title,
                                MACAddress: item["mac-address"],
                                connected: item["media-state"].toLowerCase() === "plugged",
                                enabled: item["enabled"].toLowerCase() === "true",
                                speed: item["speed"]
                            };
                            connectionsList.push(connection);
                        }
                    }
                    return connectionsList;
                } catch (err) {
                    throw createStatusObject("Could not get network connections.", err);
                }
            };
            this.verifyOption = option => {
                if (typeof option !== "string" || option === "") return rejectWithStatus("Invalid parameter 'option'.");
                let uri = "/ctrl/options/" + encodeURIComponent(option);
                return o.Network.get(uri).then(() => Promise.resolve(true)).catch(err => {
                    if (err.hasOwnProperty("httpStatus") && err.httpStatus.hasOwnProperty("code") && err.httpStatus.code === 404) return Promise.resolve(false); else return rejectWithStatus("Failed to verify option.", err);
                });
            };
            this.createBackup = (path, timeout = 60) => {
                if (typeof path !== "string" || path === "") return rejectWithStatus("Invalid path.");
                if (typeof timeout !== "number" || timeout <= 0) return rejectWithStatus("Invalid timeout.");
                let p = `/fileservice/${path}`;
                let body = `backup=${encodeURIComponent(p)}`;
                return o.Network.post("/ctrl/backup/create", body).then(res => {
                    let location = res.getResponseHeader("Location");
                    if (location !== null) {
                        return waitProgressCompletion(location, timeout).then(code => getStatusCode(code)).then(status => {
                            if (status.severity.toLowerCase() === "error") return Promise.reject({
                                message: "Progress resource reported error.",
                                controllerStatus: status
                            });
                            return Promise.resolve();
                        }).catch(err => Promise.reject(err));
                    }
                    o.writeDebug("createBackup: Failed to get the location of progress resource. The backup will be created but the call returns before it has completed.", 2);
                    return Promise.resolve();
                }).catch(err => rejectWithStatus("Backup process failed.", err));
            };
            this.verifyBackup = (path, {
                ignoreMismatches = this.BackupIgnoreMismatches.none,
                includeControllerSettings = true,
                includeSafetySettings = true,
                include = this.BackupInclude.all
            } = {}) => {
                const replacables = {
                    ACCEPTED: "ok",
                    RESTORE_MISMATCH_SYSTEM_ID: "system_id_mismatch",
                    RESTORE_MISMATCH_TEMPLATE_ID: "template_id_mismatch",
                    DIR_NOT_COMPLETE: "file_or_directory_missing",
                    CFG_DATA_INCORRECT: "cfg_file_corrupt"
                };
                const processString = function(text) {
                    if (typeof text !== "string" || text === null) return "";
                    if (replacables.hasOwnProperty(text) === false) return text.toLowerCase();
                    return replacables[text];
                };
                if (typeof path !== "string" || path === "") return rejectWithStatus("Invalid path.");
                if (ignoreMismatches !== "all" && ignoreMismatches !== "system-id" && ignoreMismatches !== "template-id" && ignoreMismatches !== "none") return rejectWithStatus("Invalid parameter 'ignoreMismatches'.");
                if (typeof includeControllerSettings !== "boolean") return rejectWithStatus("Invalid parameter 'includeControllerSettings'.");
                if (typeof includeSafetySettings !== "boolean") return rejectWithStatus("Invalid parameter 'includeSafetySettings'.");
                if (include !== "cfg" && include !== "modules" && include !== "all") return rejectWithStatus("Invalid parameter 'include'.");
                let p = `/fileservice/${path}`;
                let body = `backup=${encodeURIComponent(p)}`;
                body += "&ignore=" + encodeURIComponent(ignoreMismatches);
                body += "&include-cs=" + encodeURIComponent(includeControllerSettings.toString());
                body += "&include-ss=" + encodeURIComponent(includeSafetySettings.toString());
                body += "&include=" + encodeURIComponent(include);
                return o.Network.post("/ctrl/backup/check-restore", body).then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    let statuses = [];
                    for (const item of obj.state) {
                        if (item._type === "ctrl-checkrestore" && item["status"] !== "ACCEPTED") {
                            let status = {
                                status: processString(item["status"]),
                                path: item["path"] === undefined ? "" : item["path"]
                            };
                            statuses.push(status);
                        }
                    }
                    return Promise.resolve(statuses);
                }).catch(err => rejectWithStatus("Verify backup failed.", err));
            };
            this.restoreBackup = (path, {
                ignoreMismatches = this.BackupIgnoreMismatches.none,
                deleteDir = true,
                includeSafetySettings = true,
                include = this.BackupInclude.all
            } = {}) => {
                if (typeof path !== "string" || path === "") return rejectWithStatus("Invalid path.");
                if (ignoreMismatches !== "all" && ignoreMismatches !== "system-id" && ignoreMismatches !== "template-id" && ignoreMismatches !== "none") return rejectWithStatus("Invalid parameter 'ignoreMismatches'.");
                if (typeof deleteDir !== "boolean") return rejectWithStatus("Invalid parameter 'deleteDir'.");
                if (typeof includeSafetySettings !== "boolean") return rejectWithStatus("Invalid parameter 'includeSafetySettings'.");
                if (include !== "cfg" && include !== "modules" && include !== "all") return rejectWithStatus("Invalid parameter 'include'.");
                let p = `/fileservice/${path}`;
                let body = `backup=${encodeURIComponent(p)}`;
                body += "&ignore=" + encodeURIComponent(ignoreMismatches);
                body += "&delete-dir=" + encodeURIComponent(deleteDir.toString());
                body += "&include-ss=" + encodeURIComponent(includeSafetySettings.toString());
                body += "&include=" + encodeURIComponent(include);
                return o.Mastership.request().then(() => {
                    return o.Network.post("/ctrl/backup/restore", body).then(() => Promise.resolve("Restore started.")).catch(err => {
                        return o.Mastership.release().then(() => Promise.reject("Could not start restore. >>> " + err)).catch(err => Promise.reject("Could not start restore and failed to release mastership. >>> " + err));
                    });
                }).catch(err => rejectWithStatus("Failed to restore backup.", err));
            };
            this.compress = (srcPath, destPath, timeout = 60) => {
                if (typeof srcPath !== "string" || srcPath === "") return rejectWithStatus("Invalid 'srcPath'.");
                if (typeof destPath !== "string" || destPath === "") return rejectWithStatus("Invalid 'destPath'.");
                if (isNaN(timeout) == true || timeout < 0) return rejectWithStatus("Invalid 'timeout'.");
                let p1 = `/fileservice/${srcPath}`;
                let p2 = `/fileservice/${destPath}`;
                let body = `srcpath=${encodeURIComponent(p1)}&dstpath=${encodeURIComponent(p2)}`;
                return o.Network.post("/ctrl/compress", body).then(res => {
                    let location = res.getResponseHeader("Location");
                    if (location !== null) {
                        return waitProgressCompletion(location, timeout).then(code => getStatusCode(code)).then(status => {
                            if (status.severity.toLowerCase() === "error") return Promise.reject({
                                message: "Progress resource reported error.",
                                controllerStatus: status
                            });
                            return Promise.resolve();
                        }).catch(err => Promise.reject(err));
                    }
                    o.writeDebug("compress: Failed to get the location of progress resource. The file will be compressed but the call returns before it has completed.", 2);
                    return Promise.resolve();
                }).catch(err => rejectWithStatus("Failed to compress file.", err));
            };
            this.decompress = (srcPath, destPath, timeout = 60) => {
                if (typeof srcPath !== "string" || srcPath === "") return Promise.reject("Invalid srcPath.");
                if (typeof destPath !== "string" || destPath === "") return Promise.reject("Invalid destPath.");
                if (isNaN(timeout) == true || timeout < 0) return Promise.reject("timeout not valid.");
                let p1 = `/fileservice/${srcPath}`;
                let p2 = `/fileservice/${destPath}`;
                let body = `srcpath=${encodeURIComponent(p1)}&dstpath=${encodeURIComponent(p2)}`;
                return o.Network.post("/ctrl/decompress", body).then(res => {
                    let location = res.getResponseHeader("Location");
                    if (location !== null) {
                        return waitProgressCompletion(location, timeout).then(code => getStatusCode(code)).then(status => {
                            if (status.severity.toLowerCase() === "error") return Promise.reject({
                                message: "Progress resource reported error.",
                                controllerStatus: status
                            });
                            return Promise.resolve();
                        }).catch(err => Promise.reject(err));
                    }
                    o.writeDebug("decompress: Failed to get the location of progress resource. The file will be decompressed but the call returns before it has completed.", 2);
                    return Promise.resolve();
                }).catch(err => rejectWithStatus("Failed to decompress file.", err));
            };
            this.saveDiagnostics = async (destPath, timeout = 60) => {
                try {
                    if (await o.isVirtualController() === true) {
                        throw createStatusObject(VC_NOT_SUPPORTED);
                    }
                    if (typeof destPath !== "string" || destPath === "") {
                        throw "Invalid 'destPath'.";
                    }
                    if (isNaN(timeout) == true || timeout < 0) {
                        throw "Invalid 'timeout'.";
                    }
                    const p = `/fileservice/${destPath}`;
                    const body = `dstpath=${encodeURIComponent(p)}`;
                    const res = await o.Network.post("/ctrl/diagnostics/save", body);
                    const location = res.getResponseHeader("Location");
                    if (location !== null) {
                        const code = await waitProgressCompletion(location, timeout);
                        const status = await getStatusCode(code);
                        if (status.severity.toLowerCase() === "error") {
                            throw {
                                message: "Progress resource reported error.",
                                controllerStatus: status
                            };
                        }
                    } else {
                        throw "saveDiagnostics: Failed to get the location of progress resource. The diagnostics might be successful but the call returns before it has completed.";
                    }
                } catch (err) {
                    throw createStatusObject("Problem while save diagnostics.", err);
                }
            };
        }();
        o.FileSystem = new function() {
            const toDate = function(text) {
                try {
                    let t = text.replace(/[T]/g, "-");
                    t = t.replace(/[ ]/g, "");
                    t = t.replace(/[:]/g, "-");
                    let splits = t.split("-");
                    if (splits.length !== 6) {
                        throw new Error("Incorrect number of fields.");
                    }
                    for (let iii = 0; iii < splits.length; iii++) {
                        if (splits[iii] === "") {
                            throw new Error(`Field ${iii} is empty.`);
                        }
                    }
                    return new Date(splits[0], splits[1] - 1, splits[2], splits[3], splits[4], splits[5]);
                } catch (error) {
                    RWS.writeDebug(`Failed to convert '${text}' to date. >>> ${error}`);
                    return new Date();
                }
            };
            function Directory(path = "$HOME") {
                let dirPath = path;
                let dirContents = {
                    directories: [],
                    files: []
                };
                let isDeleted = false;
                this.getPath = function() {
                    return dirPath;
                };
                this.getProperties = function() {
                    if (isDeleted === true) return rejectWithStatus("Directory has been deleted.");
                    let path = dirPath.substring(0, dirPath.lastIndexOf("/"));
                    let dir = dirPath.substring(dirPath.lastIndexOf("/") + 1);
                    if (isNonEmptyString(path) === false) return rejectWithStatus("Could not get directory.");
                    return RWS.FileSystem.getDirectory(path).then(x1 => x1.getContents()).then(x2 => {
                        for (let item of x2.directories) {
                            if (item.name === dir) return Promise.resolve(item);
                        }
                        return Promise.reject("Directory not found.");
                    }).catch(err => rejectWithStatus(err));
                };
                this.getContents = function() {
                    if (isDeleted === true) return rejectWithStatus("Directory has been deleted.");
                    if (dirContents !== null) return Promise.resolve(dirContents);
                    return this.fetch().then(() => Promise.resolve(dirContents)).catch(err => rejectWithStatus(err));
                };
                this.delete = function() {
                    if (isDeleted === true) return rejectWithStatus("Directory has been deleted.");
                    if (isNonEmptyString(dirPath) === false) return rejectWithStatus("Directory's path is not a valid string.");
                    let path = `/fileservice/${encodePath(dirPath)}`;
                    return o.Network.delete(path).then(() => {
                        isDeleted = true;
                        return Promise.resolve();
                    }).catch(err => rejectWithStatus("Failed deleting directory.", err));
                };
                this.create = function(newDirectory) {
                    if (isDeleted === true) return rejectWithStatus("Directory has been deleted.");
                    if (isNonEmptyString(newDirectory) === false) return rejectWithStatus("New directory's name is not a valid string.");
                    if (isNonEmptyString(dirPath) === false) return rejectWithStatus("Directory's path is not a valid string.");
                    let path = `/fileservice/${encodePath(dirPath)}/create`;
                    let body = `fs-newname=${encodeURIComponent(newDirectory)}`;
                    return o.Network.post(path, body).then(() => this.fetch()).then(() => RWS.FileSystem.getDirectory(`${dirPath}/${newDirectory}`)).then(dir => Promise.resolve(dir)).catch(err => rejectWithStatus("Failed creating directory.", err));
                };
                this.createFileObject = function(fileName) {
                    if (isDeleted === true) return rejectWithStatus("Directory has been deleted.");
                    if (isNonEmptyString(fileName) === false) return rejectWithStatus("New file's name is not a valid string.");
                    if (isNonEmptyString(dirPath) === false) return rejectWithStatus("Directory's path is not a valid string.");
                    return RWS.FileSystem.createFileObject(`${dirPath}/${fileName}`);
                };
                this.rename = function(newName) {
                    if (isDeleted === true) return rejectWithStatus("Directory has been deleted.");
                    if (isNonEmptyString(newName) === false) return rejectWithStatus("New directory's name is not a valid string.");
                    if (isNonEmptyString(dirPath) === false) return rejectWithStatus("Directory's path is not a valid string.");
                    let path = `/fileservice/${encodePath(dirPath)}/rename`;
                    let body = `fs-newname=${encodeURIComponent(newName)}`;
                    return o.Network.post(path, body).then(() => {
                        let splits = dirPath.split("/");
                        let path = "";
                        for (let iii = 0; iii < splits.length - 1; iii++) {
                            path += splits[iii] + "/";
                        }
                        dirPath = path + newName;
                        return Promise.resolve();
                    }).catch(err => rejectWithStatus("Failed renaming directory.", err));
                };
                this.copy = function(copyPath, overwrite, isRelativePath = true) {
                    if (isDeleted === true) return rejectWithStatus("Directory has been deleted.");
                    if (isNonEmptyString(copyPath) === false) return rejectWithStatus("New directory's name is not a valid string.");
                    if (isNonEmptyString(dirPath) === false) return rejectWithStatus("Directory's path is not a valid string.");
                    if (typeof overwrite !== "boolean") return rejectWithStatus("Parameter 'overwrite' is not of valid type.");
                    if (typeof isRelativePath !== "boolean") return rejectWithStatus("Parameter 'isRelativePath' is not of valid type.");
                    let path = `/fileservice/${encodePath(dirPath)}/copy`;
                    let body = "";
                    if (isRelativePath === true) {
                        body = `fs-newname=${encodeURIComponent(copyPath)}&fs-overwrite=${overwrite}`;
                    } else {
                        let p = `/fileservice/${copyPath}`;
                        body = `fs-newname=${encodeURIComponent(p)}&fs-overwrite=${overwrite}`;
                    }
                    return o.Network.post(path, body).then(() => Promise.resolve()).catch(err => rejectWithStatus("Failed copying directory.", err));
                };
                this.fetch = function() {
                    if (isNonEmptyString(dirPath) === false) return rejectWithStatus("Directory's path is not a valid string.");
                    const getFile = item => {
                        let file = {};
                        if (item.hasOwnProperty("_title")) {
                            file["name"] = item["_title"];
                        } else {
                            file["name"] = "";
                            return file;
                        }
                        if (item.hasOwnProperty("fs-cdate")) {
                            file["created"] = toDate(item["fs-cdate"]);
                        } else {
                            file["created"] = new Date();
                        }
                        if (item.hasOwnProperty("fs-mdate")) {
                            file["modified"] = toDate(item["fs-mdate"]);
                        } else {
                            file["modified"] = new Date();
                        }
                        if (item.hasOwnProperty("fs-size")) {
                            file["size"] = parseFloat(item["fs-size"]);
                        } else {
                            file["size"] = -1;
                        }
                        if (item.hasOwnProperty("fs-readonly")) {
                            file["isReadOnly"] = item["fs-readonly"].toUpperCase() == "TRUE";
                        } else {
                            file["isReadOnly"] = false;
                        }
                        return file;
                    };
                    const getDirectory = item => {
                        let directory = {};
                        if (item.hasOwnProperty("_title")) {
                            directory["name"] = item["_title"];
                        } else {
                            directory["name"] = "";
                            return directory;
                        }
                        if (item.hasOwnProperty("fs-cdate")) {
                            directory["created"] = toDate(item["fs-cdate"]);
                        } else {
                            directory["created"] = new Date();
                        }
                        if (item.hasOwnProperty("fs-mdate")) {
                            directory["modified"] = toDate(item["fs-mdate"]);
                        } else {
                            directory["modified"] = new Date();
                        }
                        return directory;
                    };
                    const getContent = (url, content) => {
                        if (url === "") return Promise.resolve(content);
                        return o.Network.get(url).then(res => {
                            let obj = parseJSON(res.responseText);
                            if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                            if (obj._links.hasOwnProperty("next")) {
                                url = `/fileservice/${encodePath(dirPath)}/${obj._links["next"].href}`;
                            } else {
                                url = "";
                            }
                            for (const item of obj._embedded.resources) {
                                if (item["_type"] === "fs-file") {
                                    let file = getFile(item);
                                    content.files.push(file);
                                } else if (item["_type"] === "fs-dir") {
                                    let directory = getDirectory(item);
                                    content.directories.push(directory);
                                }
                            }
                            return getContent(url, content);
                        }).catch(err => Promise.reject(err));
                    };
                    let content = {
                        directories: [],
                        files: []
                    };
                    let url = `/fileservice/${encodePath(dirPath)}`;
                    return getContent(url, content).then(res => {
                        dirContents = res;
                        isDeleted = false;
                        return Promise.resolve();
                    }).catch(err => rejectWithStatus("Failed to fetch directory contents.", err));
                };
            }
            function File(path) {
                let filePath = path;
                let contentType = "";
                let contents = null;
                let isDeleted = false;
                this.getContentType = function() {
                    return contentType;
                };
                this.getProperties = function() {
                    if (isDeleted === true) return rejectWithStatus("File has been deleted.");
                    let dir = filePath.substring(0, filePath.lastIndexOf("/"));
                    let file = filePath.substring(filePath.lastIndexOf("/") + 1);
                    if (isNonEmptyString(dir) === false) return rejectWithStatus("Could not get directory.");
                    return RWS.FileSystem.getDirectory(dir).then(x1 => x1.getContents()).then(x2 => {
                        for (let item of x2.files) {
                            if (item.name === file) return Promise.resolve(item);
                        }
                        return Promise.reject("File not found.");
                    }).catch(err => rejectWithStatus(err));
                };
                this.getContents = function() {
                    if (isDeleted === true) return rejectWithStatus("File has been deleted.");
                    if (contents !== null) return Promise.resolve(contents);
                    return this.fetch().then(() => Promise.resolve(contents)).catch(err => rejectWithStatus(err));
                };
                this.setContents = function(newContents = "") {
                    if (isDeleted === true) {
                        writeDebug("File has been deleted.");
                        return false;
                    }
                    if (newContents === null) {
                        writeDebug("Contents can not be null.");
                        return false;
                    }
                    contents = newContents;
                    return true;
                };
                this.fileExists = function() {
                    let url = `/fileservice/${encodePath(filePath)}`;
                    return o.Network.head(url).then(() => {
                        isDeleted = false;
                        return Promise.resolve(true);
                    }).catch(err => {
                        if (err.hasOwnProperty("httpStatus") === true && err.httpStatus.code === 404) {
                            return Promise.resolve(false);
                        }
                        return rejectWithStatus("Failed checking file exist.", err);
                    });
                };
                this.save = async function(overwrite, isBinary = false) {
                    if (isDeleted === true) return rejectWithStatus("File has been deleted.");
                    if (isNonEmptyString(filePath) === false) return rejectWithStatus("File's path is not a valid string.");
                    if (typeof overwrite !== "boolean") return rejectWithStatus("Parameter 'overwrite' is not of valid type.");
                    if (typeof isBinary !== "boolean") return rejectWithStatus("Parameter 'isBinary' is not of valid type.");
                    let url = `/fileservice/${encodePath(filePath)}`;
                    let body = contents;
                    if (overwrite === false) {
                        let status = await this.fileExists().then(x1 => Promise.resolve(x1)).catch(err => rejectWithStatus(`Save file failed.`, err));
                        if (status === true) return rejectWithStatus(`File '${filePath}' already exists.`);
                    }
                    let contentType = {};
                    if (isBinary === true) {
                        contentType["Content-Type"] = "application/octet-stream;v=2.0";
                    } else {
                        contentType["Content-Type"] = "text/plain;v=2.0";
                    }
                    return o.Network.send("PUT", url, contentType, body).then(() => Promise.resolve()).catch(err => rejectWithStatus("Failed saving file.", err));
                };
                this.delete = function() {
                    if (isDeleted === true) return rejectWithStatus("File has been deleted.");
                    if (isNonEmptyString(filePath) === false) return rejectWithStatus("File's path is not a valid string.");
                    let path = `/fileservice/${encodePath(filePath)}`;
                    return o.Network.delete(path).then(() => {
                        isDeleted = true;
                        return Promise.resolve();
                    }).catch(err => rejectWithStatus("Failed deleting file.", err));
                };
                this.rename = function(newName) {
                    if (isDeleted === true) return rejectWithStatus("File has been deleted.");
                    if (isNonEmptyString(newName) === false) return rejectWithStatus("New file's name is not a valid string.");
                    if (isNonEmptyString(filePath) === false) return rejectWithStatus("File's path is not a valid string.");
                    let path = `/fileservice/${encodePath(filePath)}/rename`;
                    let body = `fs-newname=${encodeURIComponent(newName)}`;
                    return o.Network.post(path, body).then(() => Promise.resolve()).catch(err => rejectWithStatus("Failed renaming file.", err));
                };
                this.copy = function(copyName, overwrite, isRelativePath = true) {
                    if (isDeleted === true) return rejectWithStatus("File has been deleted.");
                    if (isNonEmptyString(copyName) === false) return rejectWithStatus("New file's name is not a valid string.");
                    if (typeof overwrite !== "boolean") return rejectWithStatus("Parameter 'overwrite' is not of valid type.");
                    if (typeof isRelativePath !== "boolean") return rejectWithStatus("Parameter 'isRelativePath' is not of valid type.");
                    if (isNonEmptyString(filePath) === false) return rejectWithStatus("File's path is not a valid string.");
                    let path = `/fileservice/${encodePath(filePath)}/copy`;
                    let body = "";
                    if (isRelativePath === true) {
                        body = `fs-newname=${encodeURIComponent(copyName)}&fs-overwrite=${overwrite}`;
                    } else {
                        let p = `/fileservice/${copyName}`;
                        body = `fs-newname=${encodeURIComponent(p)}&fs-overwrite=${overwrite}`;
                    }
                    return o.Network.post(path, body).then(() => Promise.resolve()).catch(err => rejectWithStatus("Failed copying file.", err));
                };
                this.fetch = function() {
                    if (isNonEmptyString(filePath) === false) return rejectWithStatus("File's path is not a valid string.");
                    let path = `/fileservice/${encodePath(filePath)}`;
                    return o.Network.get(path).then(res => {
                        contentType = res.getResponseHeader("content-type");
                        contents = res.responseText;
                        isDeleted = false;
                        return Promise.resolve();
                    }).catch(err => rejectWithStatus("Failed fetching contents.", err));
                };
            }
            this.getDirectory = function(directoryPath) {
                if (isNonEmptyString(directoryPath) === false) return rejectWithStatus(`Parameter 'directoryPath' is not a valid string.`);
                let directory = new Directory(directoryPath);
                return directory.fetch().then(() => Promise.resolve(directory)).catch(err => Promise.reject(err));
            };
            this.createDirectory = function(directoryPath) {
                if (isNonEmptyString(directoryPath) === false) return rejectWithStatus(`Parameter 'directoryPath' is not a valid string.`);
                let replaced = directoryPath.replace("\\", "/");
                let path = replaced.substring(0, replaced.lastIndexOf("/"));
                let newDirectory = replaced.substring(replaced.lastIndexOf("/") + 1);
                let directory = new Directory(path);
                return directory.create(newDirectory);
            };
            this.getFile = function(filePath) {
                if (isNonEmptyString(filePath) === false) return rejectWithStatus(`Parameter 'filePath' is not a valid string.`);
                let file = new File(filePath);
                return file.fetch().then(() => Promise.resolve(file)).catch(err => Promise.reject(err));
            };
            this.createFileObject = function(filePath) {
                if (isNonEmptyString(filePath) === false) return rejectWithStatus(`Parameter 'filePath' is not a valid string.`);
                return new File(filePath);
            };
        }();
        o.Elog = new function() {
            this.EventType = {
                informational: "informational",
                warning: "warning",
                error: "error"
            };
            this.DomainId = {
                common: 0,
                operational: 1,
                system: 2,
                hardware: 3,
                program: 4,
                motion: 5,
                io: 7,
                user: 8,
                safety: 9,
                internal: 10,
                process: 11,
                configuration: 12,
                rapid: 15,
                connectedServices: 17
            };
            function Event(number, language = "en") {
                var sequenceNumber = number;
                var languageId = language;
                var eventType = null;
                var timeStamp = null;
                var code = null;
                var title = null;
                var description = null;
                var consequences = null;
                var causes = null;
                var actions = null;
                var args = [];
                this.getContents = function() {
                    if (this.isValid() === true) {
                        return Promise.resolve({
                            sequenceNumber: sequenceNumber,
                            eventType: eventType,
                            timeStamp: timeStamp,
                            code: code,
                            title: title,
                            description: description,
                            consequences: consequences,
                            causes: causes,
                            actions: actions,
                            arguments: args
                        });
                    }
                    return fetch().then(() => {
                        return Promise.resolve({
                            sequenceNumber: sequenceNumber,
                            eventType: eventType,
                            timeStamp: timeStamp,
                            code: code,
                            title: title,
                            description: description,
                            consequences: consequences,
                            causes: causes,
                            actions: actions,
                            arguments: args
                        });
                    }).catch(err => Promise.reject(err));
                };
                this.isValid = function() {
                    if (typeof sequenceNumber !== "number" || sequenceNumber < 0) return false;
                    if (typeof languageId !== "string" || languageId === "") return false;
                    if (typeof eventType !== "string" || eventType === null) return false;
                    if (timeStamp instanceof Date === false || timeStamp === null) return false;
                    if (typeof code !== "number" || code === null) return false;
                    if (typeof title !== "string" || title === null) return false;
                    if (typeof description !== "string" || description === null) return false;
                    if (typeof consequences !== "string" || consequences === null) return false;
                    if (typeof causes !== "string" || causes === null) return false;
                    if (typeof actions !== "string" || actions === null) return false;
                    return true;
                };
                function parseDateTime(text) {
                    if (typeof text !== "string" || text === "") return null;
                    try {
                        let s = text.replace(/[T]/g, "-");
                        s = s.replace(/[ ]/g, "");
                        s = s.replace(/[:]/g, "-");
                        let splits = s.split("-");
                        return new Date(splits[0], splits[1] - 1, splits[2], splits[3], splits[4], splits[5]);
                    } catch (error) {
                        o.writeDebug("Failed parsing date.");
                        return null;
                    }
                }
                function fetch() {
                    if (typeof sequenceNumber !== "number" || sequenceNumber < 0) return rejectWithStatus("Illegal sequence number.");
                    let url = `/rw/elog/seqnum/${encodeURIComponent(sequenceNumber)}?lang=${encodeURIComponent(languageId)}`;
                    return o.Network.get(url).then(res => {
                        if (res.status === 204) return Promise.reject(`Event with sequence number '${sequenceNumber}' not found.`);
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        for (const item of obj.state) {
                            if (item._type === "elog-message") {
                                switch (item.msgtype) {
                                  case "1":
                                    eventType = "informational";
                                    break;

                                  case "2":
                                    eventType = "warning";
                                    break;

                                  case "3":
                                    eventType = "error";
                                    break;

                                  default:
                                    eventType = item.msgtype;
                                    break;
                                }
                                timeStamp = parseDateTime(item.tstamp);
                                code = parseInt(item.code);
                                title = item.title;
                                description = item.desc;
                                consequences = item.conseqs;
                                causes = item.causes;
                                actions = item.actions;
                                if (item.hasOwnProperty("argv")) {
                                    for (const argument of item.argv) {
                                        args.push({
                                            type: argument.type,
                                            value: argument.value
                                        });
                                    }
                                }
                                break;
                            }
                        }
                        return Promise.resolve();
                    }).catch(err => rejectWithStatus("Failed to get event info.", err));
                }
            }
            function Domain(number) {
                var domainNumber = number;
                var bufferSize = -1;
                this.getDomainNumber = function() {
                    return domainNumber;
                };
                this.clearElog = () => {
                    if (typeof domainNumber !== "number" || domainNumber < 0) return rejectWithStatus("Illegal domain number.");
                    let body = "";
                    let url = `/rw/elog/${encodeURIComponent(domainNumber)}/clear`;
                    return o.Network.post(url, body).then(() => Promise.resolve()).catch(err => rejectWithStatus("Failed to clear elog.", err));
                };
                this.getNumberOfEvents = () => {
                    if (typeof domainNumber !== "number" || domainNumber < 0) return rejectWithStatus("Illegal domain number.");
                    let url = `/rw/elog/${encodeURIComponent(domainNumber)}?resource=info`;
                    return o.Network.get(url).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        let buffSize = 0;
                        let numOfEvents = 0;
                        for (const item of obj._embedded.resources) {
                            if (item._type === "elog-domain") {
                                buffSize = item.buffsize;
                                numOfEvents = item.numevts;
                                break;
                            }
                        }
                        bufferSize = parseInt(buffSize);
                        numOfEvents = parseInt(numOfEvents);
                        return Promise.resolve(numOfEvents);
                    }).catch(err => rejectWithStatus("Failed getting number of events.", err));
                };
                this.getBufferSize = function() {
                    if (typeof domainNumber !== "number" || domainNumber < 0) return rejectWithStatus("Illegal domain number.");
                    if (bufferSize < 0) {
                        return this.getNumberOfEvents().then(() => Promise.resolve(bufferSize)).catch(err => Promise.reject(err));
                    }
                    return Promise.resolve(bufferSize);
                };
                this.getEvents = (language = "en") => {
                    if (typeof domainNumber !== "number" || domainNumber < 0) return rejectWithStatus("Illegal domain number.");
                    let events = {};
                    return this.getEventsPaged(language, 200, 1).then(x => {
                        for (let item in x.events) {
                            events[item] = x.events[item];
                        }
                        if (x.numberOfPages > 1) {
                            let calls = [];
                            for (let iii = 2; iii <= x.numberOfPages; iii++) {
                                calls.push(this.getEventsPaged(language, 200, iii));
                            }
                            return Promise.all(calls).then(res => {
                                res.sort((a, b) => {
                                    return a.page - b.page;
                                });
                                for (let e of res) {
                                    for (let item in e.events) {
                                        events[item] = e.events[item];
                                    }
                                }
                                return Promise.resolve(events);
                            }).catch(err => Promise.reject(err));
                        }
                        return Promise.resolve(events);
                    }).catch(err => Promise.reject(err));
                };
                this.getEventsPaged = (language = "en", count = 50, page = 1) => {
                    if (typeof domainNumber !== "number" || domainNumber < 0) return rejectWithStatus("Illegal domain number.");
                    if (typeof count !== "number" || count < 0) count = 50;
                    if (count > 200) count = 200;
                    if (typeof page !== "number" || page < 0) return rejectWithStatus("Illegal page number.");
                    let url = `/rw/elog/${encodeURIComponent(domainNumber)}?start=${encodeURIComponent(page)}&limit=${encodeURIComponent(count)}`;
                    return o.Network.get(url).then(res => {
                        let obj = parseJSON(res.responseText);
                        if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                        let numOfPages = page;
                        if (obj._links.hasOwnProperty("last") === true) {
                            let splits = obj._links.last.href.split("?")[1].split("&");
                            for (let s of splits) {
                                if (s.startsWith("start=")) {
                                    numOfPages = parseInt(s.replace("start=", ""));
                                    break;
                                }
                            }
                        }
                        let events = {};
                        for (const item of obj._embedded.resources) {
                            if (item._type === "elog-message-li") {
                                let splits = item._links.self.href.split("/");
                                let seqNum = parseInt(splits[1]);
                                events[seqNum] = new Event(seqNum, language);
                            }
                        }
                        return Promise.resolve({
                            page: page,
                            numberOfPages: numOfPages,
                            requestedCount: count,
                            events: events
                        });
                    }).catch(err => rejectWithStatus("Failed getting events.", err));
                };
                var callbacks = [];
                this.addCallbackOnChanged = function(callback) {
                    if (typeof callback !== "function") throw new Error("callback is not a valid function");
                    callbacks.push(callback);
                };
                this.onchanged = function(newValue) {
                    let seqnum = newValue["seqnum"];
                    let num = Number.parseInt(seqnum);
                    for (let iii = 0; iii < callbacks.length; iii++) {
                        try {
                            callbacks[iii](num);
                        } catch (error) {
                            o.writeDebug(`Elog.Domain callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                this.getTitle = function() {
                    return `/rw/elog/${encodeURIComponent(domainNumber)}`;
                };
                this.getResourceString = function() {
                    return `/rw/elog/${encodeURIComponent(domainNumber)}`;
                };
                this.subscribe = function() {
                    return o.Subscriptions.subscribe([ this ]);
                };
                this.unsubscribe = function() {
                    return o.Subscriptions.unsubscribe([ this ]);
                };
            }
            this.clearElogAll = () => {
                return o.Network.post("/rw/elog/clearall").then(() => Promise.resolve()).catch(err => rejectWithStatus("Failed to clear elogs.", err));
            };
            this.clearElog = domainNumber => {
                return new Domain(domainNumber).clearElog();
            };
            this.getBufferSize = domainNumber => {
                return new Domain(domainNumber).getBufferSize();
            };
            this.getNumberOfEvents = domainNumber => {
                return new Domain(domainNumber).getNumberOfEvents();
            };
            this.getEvents = (domainNumber, language = "en") => {
                return new Domain(domainNumber).getEvents(language);
            };
            this.getEventsPaged = (domainNumber, language = "en", count = 50, page = 1) => {
                return new Domain(domainNumber).getEventsPaged(language, count, page);
            };
            this.getEvent = (sequenceNumber, language = "en") => {
                return new Event(sequenceNumber, language);
            };
            this.getDomain = function(domainNumber) {
                return new Domain(domainNumber);
            };
        }();
        o.UAS = new function() {
            let currentUserInfo = null;
            this.getUser = () => {
                if (currentUserInfo !== null) return Promise.resolve(currentUserInfo);
                return o.Network.get("/users/login-info").then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    let info = {};
                    for (const item of obj.state) {
                        if (item._type === "user-login-info") {
                            info["alias"] = item["user-alias"];
                            info["name"] = item["user-name"];
                            info["locale"] = item["user-locale"].toLowerCase();
                            info["application"] = item["user-application"];
                            info["location"] = item["user-location"];
                            break;
                        }
                    }
                    if (Object.keys(info).length !== 5) throw new Error("Could not get complete user info.");
                    currentUserInfo = info;
                    return Promise.resolve(currentUserInfo);
                }).catch(err => rejectWithStatus("Failed to get user info.", err));
            };
            this.getGrants = () => {
                return o.Network.get("/uas/grants").then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    let grants = {};
                    for (const item of obj.state) {
                        if (item._type === "grant-info") {
                            let grant = {};
                            grant["reference"] = item["grant-name"];
                            grant["name"] = item["display-name"];
                            grant["description"] = item["grant-description"];
                            grants[item["grant-name"]] = grant;
                        }
                    }
                    return Promise.resolve(grants);
                }).catch(err => rejectWithStatus("Failed to get grants.", err));
            };
            this.hasGrant = grant => {
                if (isNonEmptyString(grant) === false) return rejectWithStatus("Failed to verify grant", "Inparameter 'grant' is not a valid string.");
                return o.Network.get(`/users/grant-exists?grant=${encodeURIComponent(grant)}`).then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    let status = false;
                    for (const item of obj.state) {
                        if (item._type === "user-grant-status") {
                            status = item["status"].toLowerCase() === "true";
                            break;
                        }
                    }
                    return Promise.resolve(status);
                }).catch(err => {
                    if (err.hasOwnProperty("httpStatus") && err.httpStatus.code === 400) {
                        if (err.hasOwnProperty("controllerStatus") && err.controllerStatus.name === "SYS_CTRL_E_INVALID_GRANT") {
                            return Promise.resolve(false);
                        }
                    }
                    return rejectWithStatus("Failed to verify grant.", err);
                });
            };
            this.hasRole = role => {
                if (isNonEmptyString(role) === false) return rejectWithStatus("Failed to verify role", "Inparameter 'role' is not a valid string.");
                return this.getUser().then(() => o.Network.get(`/uas/users/${encodeURIComponent(currentUserInfo.name)}/roles`)).then(res => {
                    let obj = parseJSON(res.responseText);
                    if (typeof obj === "undefined") return Promise.reject("Could not parse JSON.");
                    for (const item of obj.state) {
                        if (item._type === "user-role") {
                            if (item["rolename"].toLowerCase() === role.toLowerCase()) return Promise.resolve(true);
                        }
                    }
                    return Promise.resolve(false);
                }).catch(err => rejectWithStatus("Failed to verify role.", err));
            };
        }();
        o.Subscriptions = new function() {
            var websocket = null;
            var websocketLocation = null;
            var subscriptionGroup = null;
            var currentSubscriptions = {};
            var timeoutID = null;
            const SOCKET_CLOSE_INTERVAL = 500;
            const SOCKET_CLOSE_RETRY_COUNT = 20;
            const wait = time => new Promise(resolve => setTimeout(resolve, time));
            const waitSocketRemoved = async loops => {
                if (loops <= 0) return Promise.reject("WebSocket closing timeout.");
                if (websocket === null) return Promise.resolve();
                if (websocket !== null && (websocket.readyState === WebSocket.CLOSED || websocket.readyState === WebSocket.CLOSING)) {
                    await wait(SOCKET_CLOSE_INTERVAL).then(() => waitSocketRemoved(loops - 1));
                }
            };
            this.connectWebsocket = () => {
                return new Promise((resolve, reject) => {
                    if (websocketLocation == null || subscriptionGroup == null) {
                        reject("No websocket location");
                        return;
                    }
                    websocket = new WebSocket(websocketLocation, "rws_subscription");
                    websocket.onopen = function(evt) {
                        o.writeDebug("WebSocket connected");
                        clearTimeout(timeoutID);
                        timeoutID = null;
                        resolve("Created Websocket!");
                    };
                    websocket.onmessage = function(evt) {
                        let parser = new DOMParser();
                        let data = parser.parseFromString(evt.data, "text/xml");
                        let listitems = data.getElementsByTagName("li");
                        if (listitems.length <= 0) return;
                        for (let iii = 0; iii < listitems.length; iii++) {
                            let event = listitems[iii];
                            let itemClass = event.getAttribute("class");
                            if (itemClass === null) continue;
                            let subResource = "";
                            if (itemClass === "rap-ui-ev") {
                                subResource = "/rw/rapid/uiinstr;uievent";
                            } else if (itemClass === "msh-resource-value") {
                                subResource = `/rw/mastership/${event.getAttribute("title")}`;
                            } else {
                                subResource = event.getElementsByTagName("a")[0].getAttribute("href");
                            }
                            let newValue = {};
                            let items = event.getElementsByTagName("span");
                            for (let iii = 0; iii < items.length; iii++) {
                                let className = items[iii].getAttribute("class");
                                newValue[className] = items[iii].innerHTML;
                            }
                            if (subResource.startsWith("/rw/rapid/symbol/RAPID/")) {
                                subResource += ";value";
                            }
                            if (subResource.startsWith("/rw/elog/")) {
                                subResource = subResource.substring(0, subResource.lastIndexOf("/"));
                            }
                            if (currentSubscriptions.hasOwnProperty(subResource)) {
                                for (let iii = 0; iii < currentSubscriptions[subResource].length; iii++) {
                                    if (currentSubscriptions[subResource][iii].onchanged !== undefined) currentSubscriptions[subResource][iii].onchanged(newValue);
                                }
                            }
                        }
                    };
                    websocket.onclose = new function(websocketRef) {
                        this.onclose = evt => {
                            if (websocket !== websocketRef) {
                                return;
                            }
                            o.writeDebug("WebSocket closing " + subscriptionGroup);
                            if (Object.keys(currentSubscriptions).length != 0) {
                                o.writeDebug("Subscriptions found on close!");
                                o.Subscriptions.unsubscribeToAll();
                            }
                            if (websocket) {
                                websocket.onmessage = undefined;
                            }
                            websocket = null;
                            websocketLocation = null;
                            subscriptionGroup = null;
                            currentSubscriptions = {};
                            clearTimeout(timeoutID);
                            timeoutID = null;
                        };
                    }(websocket).onclose;
                    websocket.onerror = function(evt) {
                        o.writeDebug("WebSocket reports Error");
                    };
                    timeoutID = setTimeout(() => {
                        if (websocket !== null && websocket.readyState !== WebSocket.OPEN) {
                            websocket = null;
                            websocketLocation = null;
                            subscriptionGroup = null;
                            currentSubscriptions = {};
                            timeoutID = null;
                            reject("Error: Trying to connect websocket!");
                        }
                    }, 15e3);
                });
            };
            const processSubscribe = async newSubscriptions => {
                if (cleanupStarted) {
                    return rejectWithStatus("Subscription refused, app cleanup started.");
                }
                let priority = "1";
                if (websocket !== null && (websocket.readyState === WebSocket.CLOSED || websocket.readyState === WebSocket.CLOSING)) {
                    await waitSocketRemoved(SOCKET_CLOSE_RETRY_COUNT).catch(err => reject(err));
                }
                if (websocket !== null && (websocket.readyState === WebSocket.CONNECTING || websocket.readyState === WebSocket.OPEN)) {
                    let body = "";
                    for (let iii = 0; iii < newSubscriptions.length; iii++) {
                        if (newSubscriptions[iii].getResourceString === undefined || newSubscriptions[iii].getResourceString() === "") {
                            let title = newSubscriptions[iii].getTitle() !== undefined ? newSubscriptions[iii].getTitle() : "<Unknown>";
                            o.writeDebug(`Subscribe on '${title}' rejected as subscription resource string not set.`, 2);
                            continue;
                        }
                        let subscription = newSubscriptions[iii];
                        let resource = subscription.getResourceString();
                        if (currentSubscriptions[resource] !== undefined && currentSubscriptions[resource].length !== 0) {
                            currentSubscriptions[resource].push(subscription);
                        } else {
                            currentSubscriptions[resource] = [ subscription ];
                            if (iii != 0) body += "&";
                            let idx = (iii + 1).toString();
                            body += `resources=${idx}&${idx}=${encodeURIComponent(resource)}&${idx}-p=${priority}`;
                        }
                    }
                    if (body === "") {
                        return Promise.resolve("OK");
                    }
                    let url = "/subscription/" + encodeURIComponent(subscriptionGroup);
                    o.writeDebug(`Subscribe on '${url}', ${body}`, 0);
                    return o.Network.put(url, body).then(() => Promise.resolve()).catch(err => rejectWithStatus("Failed to add subscription(s).", err));
                } else {
                    currentSubscriptions = {};
                    websocketLocation = null;
                    websocket = null;
                    let body = "";
                    for (let iii = 0; iii < newSubscriptions.length; iii++) {
                        if (newSubscriptions[iii].getResourceString === undefined || newSubscriptions[iii].getResourceString() === "") {
                            let title = newSubscriptions[iii].getTitle() !== undefined ? newSubscriptions[iii].getTitle() : "<Unknown>";
                            o.writeDebug(`Subscription on '${title}' rejected as subscription resource string not set.`, 2);
                            continue;
                        }
                        let subscription = newSubscriptions[iii];
                        let resource = subscription.getResourceString();
                        if (currentSubscriptions[resource] !== undefined && currentSubscriptions[resource].length !== 0) {
                            currentSubscriptions[resource].push(subscription);
                        } else {
                            currentSubscriptions[resource] = [ subscription ];
                            if (iii != 0) body += "&";
                            let idx = (iii + 1).toString();
                            body += `resources=${idx}&${idx}=${encodeURIComponent(resource)}&${idx}-p=${priority}`;
                        }
                    }
                    let unblockCleanupProcess;
                    creatingSubscriptionGroupAndWebSocket = new Promise(resolver => {
                        unblockCleanupProcess = () => {
                            creatingSubscriptionGroupAndWebSocket = null;
                            resolver();
                        };
                    });
                    o.writeDebug(`Subscribe on '/subscription', ${body}`, 0);
                    return o.Network.post("/subscription", body).then(res => {
                        websocketLocation = res.getResponseHeader("location");
                        subscriptionGroup = websocketLocation.substring(websocketLocation.indexOf("poll/") + 5);
                        return this.connectWebsocket().then(() => {
                            return Promise.resolve("Subscribed");
                        }).catch(err => {
                            return Promise.reject(err);
                        }).finally(() => {
                            unblockCleanupProcess();
                        });
                    }).catch(err => {
                        unblockCleanupProcess();
                        return rejectWithStatus("Failed to add subscription(s).", err);
                    });
                }
            };
            const processUnsubscribe = removedSubscription => {
                if (websocket !== null && websocket.readyState !== WebSocket.OPEN) {
                    return rejectWithStatus("WebSocket not open.");
                }
                if (removedSubscription.getResourceString === undefined || removedSubscription.getResourceString() === "") {
                    let title = removedSubscription.getTitle() !== undefined ? removedSubscription.getTitle() : "<Unknown>";
                    return rejectWithStatus(`Unsubscribe on '${title}' rejected as subscription resource not set.`, 2);
                }
                let resource = removedSubscription.getResourceString();
                let array = currentSubscriptions[resource];
                if (array === undefined) {
                    return rejectWithStatus("Cannot unsubscribe from " + removedSubscription.getTitle() + " because there are no subscriptions to that signal!");
                }
                var index = array.indexOf(removedSubscription);
                if (index > -1) {
                    array.splice(index, 1);
                } else {
                    return rejectWithStatus("Cannot unsubscribe from " + removedSubscription.getTitle() + " because there are no subscriptions to that signal data object!");
                }
                if (currentSubscriptions[resource].length == 0) {
                    delete currentSubscriptions[resource];
                    let url = `/subscription/${encodeURIComponent(subscriptionGroup)}/${resource}`;
                    o.writeDebug(`Unsubscribe on '${url}'`, 0);
                    return o.Network.delete(url).then(() => {
                        if (Object.keys(currentSubscriptions) <= 0) {
                            if (websocket !== null) {
                                o.writeDebug("WebSocket closing " + subscriptionGroup);
                                websocket.onmessage = undefined;
                                websocket.close();
                                websocket = null;
                                websocketLocation = null;
                                subscriptionGroup = null;
                                currentSubscriptions = {};
                                clearTimeout(timeoutID);
                                timeoutID = null;
                            }
                        }
                        return Promise.resolve();
                    }).catch(err => rejectWithStatus("Failed to unsubscribe to subscription(s).", err));
                }
                return Promise.resolve();
            };
            var opQueue = [];
            var opBusy = false;
            function processOperation() {
                if (!opBusy && opQueue.length > 0) {
                    opBusy = true;
                    let item = opQueue.pop();
                    if (RWS.isDebugActive(0)) {
                        let op = item.operation1 === processUnsubscribe ? "Unsubscribe" : "Subscribe";
                        let d = "";
                        if (item.operation1 === processUnsubscribe) {
                            d = item.indata.getResourceString();
                        } else {
                            for (let iii = 0; iii < item.indata.length; iii++) {
                                d += item.indata[iii].getResourceString();
                                if (iii < item.indata.length - 1) d += ",";
                            }
                        }
                        o.writeDebug(`Add ${op}, '${d}'`, 0);
                    }
                    item.operation1(item.indata).then(() => {
                        if (typeof item.operation2 !== "undefined" && item.operation2 !== null) {
                            return item.operation2();
                        }
                        return Promise.resolve();
                    }).then(() => {
                        if (typeof item.resolve !== "undefined") {
                            item.resolve();
                        }
                        opBusy = false;
                        setTimeout(() => {
                            processOperation();
                        }, 0);
                    }).catch(err => {
                        o.writeDebug(`processOperation failed to run operation. >>> ${err.message}`);
                        if (typeof item.reject !== "undefined") {
                            item.reject(err);
                        }
                        opBusy = false;
                        setTimeout(() => {
                            processOperation();
                        }, 0);
                    });
                }
            }
            this.subscribe = (newSubscriptions, initialEvent = null) => {
                if (cleanupStarted) {
                    return rejectWithStatus("Subscription refused, app cleanup started.");
                } else {
                    return new Promise((resolve, reject) => {
                        opQueue.unshift({
                            resolve: resolve,
                            reject: reject,
                            operation1: processSubscribe,
                            operation2: initialEvent,
                            indata: newSubscriptions
                        });
                        setTimeout(() => {
                            processOperation();
                        }, 0);
                    });
                }
            };
            this.unsubscribe = removedSubscriptions => {
                return new Promise((resolve, reject) => {
                    for (let iii = 0; iii < removedSubscriptions.length; iii++) {
                        opQueue.unshift({
                            resolve: resolve,
                            reject: reject,
                            operation1: processUnsubscribe,
                            indata: removedSubscriptions[iii]
                        });
                    }
                    setTimeout(() => {
                        processOperation();
                    }, 0);
                });
            };
            this.unsubscribeToAll = () => {
                if (websocket !== null && websocket.readyState !== WebSocket.OPEN) {
                    return Promise.resolve();
                }
                if (subscriptionGroup != null) {
                    let subscriptionGroup_temp = subscriptionGroup;
                    websocket = null;
                    websocketLocation = null;
                    subscriptionGroup = null;
                    currentSubscriptions = {};
                    if (o.isTPUWebView()) {
                        if (o.__unload === true) {
                            postWebViewMessage("DeleteSubscriptionGroup " + subscriptionGroup_temp);
                            return Promise.resolve();
                        } else {
                            return o.Network.delete("/subscription/" + encodeURIComponent(subscriptionGroup_temp)).then(() => {
                                Promise.resolve();
                            }).catch(err => {
                                rejectWithStatus("Failed to unsubscribe to all.", err);
                            });
                        }
                    } else {
                        if (navigator.userAgent.toLowerCase().indexOf("firefox") < 0) {
                            return fetch("/subscription/" + encodeURIComponent(subscriptionGroup_temp), {
                                method: "DELETE",
                                keepalive: true,
                                headers: {
                                    Accept: "application/hal+json;v=2.0;"
                                }
                            }).then(() => {
                                Promise.resolve();
                            }).catch(err => {
                                `Failed to unsubscribe to all : ${JSON.stringify(err)}`;
                            });
                        } else {
                            return o.Network.delete("/subscription/" + encodeURIComponent(subscriptionGroup_temp)).then(() => {
                                Promise.resolve();
                            }).catch(err => {
                                rejectWithStatus("Failed to unsubscribe to all.", err);
                            });
                        }
                    }
                } else {
                    return Promise.resolve();
                }
            };
        }();
        o.Mastership = new function() {
            this.MastershipType = {
                nomaster: "nomaster",
                local: "local",
                remote: "remote"
            };
            let mastershipCounter = 0;
            let opBusy = false;
            let onRequestedListeners = [];
            let onReleasedListeners = [];
            let uid = undefined;
            function Monitor() {
                const callbacks = [];
                const raiseEvent = async () => {
                    const value = await o.Mastership.getCurrent();
                    for (const cb of callbacks) {
                        try {
                            cb(value);
                        } catch (error) {
                            o.writeDebug(`Mastership monitor callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                this.addCallbackOnChanged = callback => {
                    if (typeof callback !== "function") throw new Error("callback is not a valid function");
                    callbacks.push(callback);
                };
                this.getTitle = () => {
                    return "/rw/mastership/edit";
                };
                this.getResourceString = () => {
                    return "/rw/mastership/edit";
                };
                this.onchanged = async newValue => {
                    const value = {
                        alias: newValue.alias,
                        application: newValue.application,
                        location: newValue.location,
                        type: newValue.mastership,
                        heldbyme: newValue.uid === uid,
                        uid: newValue.uid
                    };
                    for (const cb of callbacks) {
                        try {
                            cb(value);
                        } catch (error) {
                            o.writeDebug(`Mastership monitor callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                this.subscribe = async (raiseInitial = false) => {
                    if (await o.isSpocSystem()) {
                        throw createStatusObject("Legacy mastership monitoring is not supported on RobotWare 8 or later.");
                    }
                    try {
                        if (uid === undefined) {
                            uid = JSON.parse((await o.Network.get("/users/login-info")).response).state[0]["uas-id"];
                        }
                        if (raiseInitial === true) return await o.Subscriptions.subscribe([ this ], raiseEvent);
                        return await o.Subscriptions.subscribe([ this ]);
                    } catch (e) {
                        throw createStatusObject("Error while setting up mastership subscription", e);
                    }
                };
                this.unsubscribe = async () => {
                    return await o.Subscriptions.unsubscribe([ this ]);
                };
            }
            this.getMonitor = () => {
                return new Monitor();
            };
            this.getCurrent = async () => {
                if (await o.isSpocSystem()) {
                    throw createStatusObject("Legacy mastership is not supported on RobotWare 8 or later.");
                }
                try {
                    let resp = JSON.parse((await o.Network.get("/rw/mastership/edit")).response).state[0];
                    return {
                        alias: resp.alias,
                        application: resp.application,
                        location: resp.location,
                        type: resp.mastership,
                        heldbyme: resp.mastershipheldbyme === "TRUE",
                        uid: resp.uid
                    };
                } catch (e) {
                    throw createStatusObject("Could not fetch mastership info", e);
                }
            };
            this.request = async () => {
                if (await o.isSpocSystem()) {
                    if (typeof window.appSpocWriteAccessRequired === "function") {
                        await window.appSpocWriteAccessRequired();
                    }
                    return;
                } else {
                    await (() => {
                        if (cleanupStarted) {
                            return rejectWithStatus("Mastership request refused, app cleanup started.");
                        } else {
                            try {
                                o.writeDebug("Requesting mastership..");
                                let listener = {
                                    promise: null,
                                    resolve: null,
                                    reject: null
                                };
                                listener.promise = new Promise((resolve, reject) => {
                                    listener.resolve = resolve;
                                    listener.reject = reject;
                                });
                                onRequestedListeners.push(listener);
                                if (o.isTPUWebView()) {
                                    postWebViewMessage("RequestMastership");
                                } else {
                                    setTimeout(() => {
                                        processMastership();
                                    }, 0);
                                }
                                return listener.promise;
                            } catch (error) {
                                return rejectWithStatus("Failed to get mastership.", error);
                            }
                        }
                    })();
                }
            };
            this.release = async () => {
                if (await o.isSpocSystem()) {
                    return;
                } else {
                    await (() => {
                        if (cleanupStarted) {
                            return rejectWithStatus("Mastership request refused, app cleanup started.");
                        } else {
                            try {
                                o.writeDebug("Releasing mastership..");
                                let listener = {
                                    promise: null,
                                    resolve: null,
                                    reject: null
                                };
                                listener.promise = new Promise((resolve, reject) => {
                                    listener.resolve = resolve;
                                    listener.reject = reject;
                                });
                                onReleasedListeners.push(listener);
                                if (o.isTPUWebView()) {
                                    postWebViewMessage("ReleaseMastership");
                                } else {
                                    setTimeout(() => {
                                        processMastership();
                                    }, 0);
                                }
                                return listener.promise;
                            } catch (error) {
                                return rejectWithStatus("Failed to release mastership.", error);
                            }
                        }
                    })();
                }
            };
            this.onRequested = async data => {
                let length = onRequestedListeners.length;
                try {
                    if (JSON.parse(data).success === true) {
                        for (let iii = 0; iii < length; iii++) {
                            mastershipCounter++;
                            onRequestedListeners.shift().resolve("Mastership acquired!");
                        }
                    } else {
                        for (let iii = 0; iii < length; iii++) {
                            onRequestedListeners.shift().reject("Could not acquire Mastership!");
                        }
                        o.writeDebug("Could not acquire Mastership!", 3);
                    }
                } catch (exception) {
                    for (let iii = 0; iii < length; iii++) {
                        onRequestedListeners.shift().reject(exception.message);
                    }
                    o.writeDebug("Exception: " + exception.message, 3);
                }
            };
            this.onReleased = async data => {
                let length = onReleasedListeners.length;
                try {
                    if (JSON.parse(data).success === true) {
                        for (let iii = 0; iii < length; iii++) {
                            mastershipCounter = mastershipCounter <= 1 ? 0 : mastershipCounter - 1;
                            onReleasedListeners.shift().resolve("Mastership released!");
                        }
                    } else {
                        for (let iii = 0; iii < length; iii++) {
                            onReleasedListeners.shift().reject("Could not release Mastership!");
                        }
                        o.writeDebug("Could not release Mastership!", 3);
                    }
                } catch (exception) {
                    for (let iii = 0; iii < length; iii++) {
                        onReleasedListeners.shift().reject(exception.message);
                    }
                    o.writeDebug("Exception: " + exception.message, 3);
                }
            };
            async function processMastership() {
                try {
                    if (opBusy === false && onRequestedListeners.length > 0) {
                        opBusy = true;
                        let item = onRequestedListeners.pop();
                        if (cleanupStarted) {
                            item.reject(createStatusObject("Mastership request refused, app cleanup started."));
                            return;
                        }
                        if (++mastershipCounter > 1) {
                            item.resolve();
                        } else {
                            await o.Network.send("POST", "/rw/mastership/edit/request", {
                                "Content-Type": "application/x-www-form-urlencoded;v=2.0"
                            }).then(() => item.resolve()).catch(err => {
                                mastershipCounter = mastershipCounter <= 1 ? 0 : mastershipCounter - 1;
                                o.writeDebug("Could not acquire Mastership. >>> " + err.message);
                                item.reject(createStatusObject("Could not acquire Mastership.", err));
                            });
                        }
                        opBusy = false;
                        setTimeout(() => processMastership(), 0);
                    } else if (opBusy === false && onReleasedListeners.length > 0) {
                        opBusy = true;
                        let item = onReleasedListeners.pop();
                        if (mastershipCounter < 1) {
                            o.writeDebug("Releasing mastership, though counter is 0.", 1);
                        }
                        mastershipCounter = mastershipCounter <= 1 ? 0 : mastershipCounter - 1;
                        if (mastershipCounter > 0) {
                            item.resolve();
                        } else {
                            await o.Network.send("POST", "/rw/mastership/edit/release", {
                                "Content-Type": "application/x-www-form-urlencoded;v=2.0"
                            }).then(() => item.resolve()).catch(err => {
                                o.writeDebug("Could not release Mastership. >>> " + err.message);
                                item.reject(createStatusObject("Could not release Mastership.", err));
                            });
                        }
                        opBusy = false;
                        setTimeout(() => processMastership(), 0);
                    }
                } catch (error) {
                    o.writeDebug(`Failed to process mastership operation. >>> ${error}`, 2);
                    opBusy = false;
                    setTimeout(() => processMastership(), 0);
                }
            }
            this.releaseAll = () => {
                if (isSpocResult !== false) {
                    return;
                }
                try {
                    let count = mastershipCounter;
                    if (o.isTPUWebView()) {
                        for (let iii = 0; iii < count; iii++) {
                            postWebViewMessage("ReleaseMastership");
                        }
                    } else {
                        mastershipCounter = 0;
                        if (navigator.userAgent.toLowerCase().indexOf("firefox") >= 0) {
                            o.Network.post("/rw/mastership/edit/release");
                        } else {
                            return fetch("/rw/mastership/edit/release", {
                                method: "POST",
                                keepalive: true,
                                headers: {
                                    Accept: "application/hal+json;v=2.0;",
                                    "Content-Type": "application/x-www-form-urlencoded;v=2.0"
                                }
                            }).then(() => {
                                Promise.resolve();
                            }).catch(err => {
                                `Failed to release all mastership: ${JSON.stringify(err)}`;
                            });
                        }
                    }
                    return Promise.resolve();
                } catch (error) {
                    return rejectWithStatus("Failed to release all mastership requests.", error);
                }
            };
        }();
        o.MotionMastership = new function() {
            this.MastershipType = {
                nomaster: "nomaster",
                local: "local",
                remote: "remote"
            };
            let motionMastershipCounter = 0;
            let opBusy = false;
            let onRequestedListeners = [];
            let onReleasedListeners = [];
            let uid = undefined;
            function Monitor() {
                const callbacks = [];
                const raiseEvent = async () => {
                    const value = await o.MotionMastership.getCurrent();
                    for (const cb of callbacks) {
                        try {
                            cb(value);
                        } catch (error) {
                            o.writeDebug(`MotionMastership monitor callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                this.addCallbackOnChanged = callback => {
                    if (typeof callback !== "function") throw new Error("callback is not a valid function");
                    callbacks.push(callback);
                };
                this.getTitle = () => {
                    return "/rw/mastership/motion";
                };
                this.getResourceString = () => {
                    return "/rw/mastership/motion";
                };
                this.onchanged = async newValue => {
                    const value = {
                        alias: newValue.alias,
                        application: newValue.application,
                        location: newValue.location,
                        type: newValue.mastership,
                        heldbyme: newValue.uid === uid,
                        uid: newValue.uid
                    };
                    for (const cb of callbacks) {
                        try {
                            cb(value);
                        } catch (error) {
                            o.writeDebug(`MotionMastership monitor callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                this.subscribe = async (raiseInitial = false) => {
                    if (await o.isSpocSystem()) {
                        throw createStatusObject("Legacy mastership monitoring is not supported on RobotWare 8 or later.");
                    }
                    try {
                        if (uid === undefined) {
                            uid = JSON.parse((await o.Network.get("/users/login-info")).response).state[0]["uas-id"];
                        }
                        if (raiseInitial === true) return await o.Subscriptions.subscribe([ this ], raiseEvent);
                        return await o.Subscriptions.subscribe([ this ]);
                    } catch (e) {
                        throw createStatusObject("Error while setting up motion mastership subscription", e);
                    }
                };
                this.unsubscribe = async () => {
                    return await o.Subscriptions.unsubscribe([ this ]);
                };
            }
            this.getMonitor = () => {
                return new Monitor();
            };
            this.getCurrent = async () => {
                if (await o.isSpocSystem()) {
                    throw createStatusObject("Legacy mastership is not supported on RobotWare 8 or later.");
                }
                try {
                    let resp = JSON.parse((await o.Network.get("/rw/mastership/motion")).response).state[0];
                    return {
                        alias: resp.alias,
                        application: resp.application,
                        location: resp.location,
                        type: resp.mastership,
                        heldbyme: resp.mastershipheldbyme === "TRUE",
                        uid: resp.uid
                    };
                } catch (e) {
                    throw createStatusObject("Could not fetch motion mastership info", e);
                }
            };
            this.request = async () => {
                if (await o.isSpocSystem()) {
                    if (typeof window.appSpocWriteAccessRequired === "function") {
                        await window.appSpocWriteAccessRequired();
                    }
                    return;
                } else {
                    await (() => {
                        if (cleanupStarted) {
                            return rejectWithStatus("Motion mastership request refused, app cleanup started.");
                        } else {
                            try {
                                o.writeDebug("Requesting motion mastership..");
                                let listener = {
                                    promise: null,
                                    resolve: null,
                                    reject: null
                                };
                                listener.promise = new Promise((resolve, reject) => {
                                    listener.resolve = resolve;
                                    listener.reject = reject;
                                });
                                onRequestedListeners.push(listener);
                                if (o.isTPUWebView()) {
                                    postWebViewMessage("RequestMotionMastership");
                                } else {
                                    setTimeout(() => {
                                        processMotionMastership();
                                    }, 0);
                                }
                                return listener.promise;
                            } catch (error) {
                                return rejectWithStatus("Failed to get motion mastership.", error);
                            }
                        }
                    })();
                }
            };
            this.release = async () => {
                if (await o.isSpocSystem()) {
                    return;
                } else {
                    await (() => {
                        if (cleanupStarted) {
                            return rejectWithStatus("Mastership request refused, app cleanup started.");
                        } else {
                            try {
                                o.writeDebug("Releasing motion mastership..");
                                let listener = {
                                    promise: null,
                                    resolve: null,
                                    reject: null
                                };
                                listener.promise = new Promise((resolve, reject) => {
                                    listener.resolve = resolve;
                                    listener.reject = reject;
                                });
                                onReleasedListeners.push(listener);
                                if (o.isTPUWebView()) {
                                    postWebViewMessage("ReleaseMotionMastership");
                                } else {
                                    setTimeout(() => {
                                        processMotionMastership();
                                    }, 0);
                                }
                                return listener.promise;
                            } catch (error) {
                                return rejectWithStatus("Failed to release motion mastership.", error);
                            }
                        }
                    })();
                }
            };
            this.onRequested = async data => {
                let length = onRequestedListeners.length;
                try {
                    if (JSON.parse(data).success === true) {
                        for (let iii = 0; iii < length; iii++) {
                            motionMastershipCounter++;
                            onRequestedListeners.shift().resolve("Motion mastership acquired!");
                        }
                    } else {
                        for (let iii = 0; iii < length; iii++) {
                            onRequestedListeners.shift().reject("Could not acquire motion mastership!");
                        }
                        o.writeDebug("Could not acquire motion mastership!", 3);
                    }
                } catch (exception) {
                    for (let iii = 0; iii < length; iii++) {
                        onRequestedListeners.shift().reject(exception.message);
                    }
                    o.writeDebug("Exception: " + exception.message, 3);
                }
            };
            this.onReleased = async data => {
                let length = onReleasedListeners.length;
                try {
                    if (JSON.parse(data).success === true) {
                        for (let iii = 0; iii < length; iii++) {
                            motionMastershipCounter = motionMastershipCounter <= 1 ? 0 : motionMastershipCounter - 1;
                            onReleasedListeners.shift().resolve("Motion mastership released!");
                        }
                    } else {
                        for (let iii = 0; iii < length; iii++) {
                            onReleasedListeners.shift().reject("Could not release motion mastership!");
                        }
                        o.writeDebug("Could not release motion mastership!", 3);
                    }
                } catch (exception) {
                    for (let iii = 0; iii < length; iii++) {
                        onReleasedListeners.shift().reject(exception.message);
                    }
                    o.writeDebug("Exception: " + exception.message, 3);
                }
            };
            async function processMotionMastership() {
                try {
                    if (opBusy === false && onRequestedListeners.length > 0) {
                        opBusy = true;
                        let item = onRequestedListeners.pop();
                        if (cleanupStarted) {
                            item.reject(createStatusObject("Motion mastership request refused, app cleanup started."));
                            return;
                        }
                        if (++motionMastershipCounter > 1) {
                            item.resolve();
                        } else {
                            await o.Network.send("POST", "/rw/mastership/motion/request", {
                                "Content-Type": "application/x-www-form-urlencoded;v=2.0"
                            }).then(() => item.resolve()).catch(err => {
                                motionMastershipCounter = motionMastershipCounter <= 1 ? 0 : motionMastershipCounter - 1;
                                o.writeDebug("Could not acquire motion mastership. >>> " + err.message);
                                item.reject(createStatusObject("Could not acquire motion mastership.", err));
                            });
                        }
                        opBusy = false;
                        setTimeout(() => processMotionMastership(), 0);
                    } else if (opBusy === false && onReleasedListeners.length > 0) {
                        opBusy = true;
                        let item = onReleasedListeners.pop();
                        if (motionMastershipCounter < 1) {
                            o.writeDebug("Releasing motion mastership, though counter is 0.", 1);
                        }
                        motionMastershipCounter = motionMastershipCounter <= 1 ? 0 : motionMastershipCounter - 1;
                        if (motionMastershipCounter > 0) {
                            item.resolve();
                        } else {
                            await o.Network.send("POST", "/rw/mastership/motion/release", {
                                "Content-Type": "application/x-www-form-urlencoded;v=2.0"
                            }).then(() => item.resolve()).catch(err => {
                                o.writeDebug("Could not release motion mastership. >>> " + err.message);
                                item.reject(createStatusObject("Could not release motion mastership.", err));
                            });
                        }
                        opBusy = false;
                        setTimeout(() => processMotionMastership(), 0);
                    }
                } catch (error) {
                    o.writeDebug(`Failed to process motion mastership operation. >>> ${error}`, 2);
                    opBusy = false;
                    setTimeout(() => processMotionMastership(), 0);
                }
            }
            this.releaseAll = () => {
                if (isSpocResult !== false) {
                    return;
                }
                try {
                    let count = motionMastershipCounter;
                    if (o.isTPUWebView()) {
                        for (let iii = 0; iii < count; iii++) {
                            postWebViewMessage("ReleaseMotionMastership");
                        }
                    } else {
                        motionMastershipCounter = 0;
                        if (navigator.userAgent.toLowerCase().indexOf("firefox") >= 0) {
                            o.Network.post("/rw/mastership/motion/release");
                        } else {
                            return fetch("/rw/mastership/motion/release", {
                                method: "POST",
                                keepalive: true,
                                headers: {
                                    Accept: "application/hal+json;v=2.0;",
                                    "Content-Type": "application/x-www-form-urlencoded;v=2.0"
                                }
                            }).then(() => {
                                Promise.resolve();
                            }).catch(err => {
                                `Failed to release all motion mastership: ${JSON.stringify(err)}`;
                            });
                        }
                    }
                    return Promise.resolve();
                } catch (error) {
                    return rejectWithStatus("Failed to release all motion mastership requests.", error);
                }
            };
        }();
        o.ControlStation = new function() {
            this.MonitorResources = {
                writeAccessStatus: "write-access-status",
                releaseAppealCounter: "release-appeal-counter",
                tpuSafetyProtocolConnected: "tpu-safety-protocol-connected",
                localIsConnected: "local-is-connected"
            };
            this.ControlStationType = {
                none: "none",
                local: "local",
                remote: "remote"
            };
            const checkSpoc = async () => {
                if (!await o.isSpocSystem()) {
                    throw "ControlStation functionality is only available on RobotWare 8 or later.";
                }
            };
            const checkNotTPU = () => {
                if (o.isTPUWebView()) {
                    throw "ControlStation functionality limited on FlexPendant (TPU).";
                }
            };
            let currentRemoteId = null;
            function Monitor(resource) {
                if (!Object.values(o.ControlStation.MonitorResources).includes(resource)) {
                    const msg = `Unable to create ControlStation Monitor: Illegal resource: ${resource}`;
                    o.writeDebug(msg, 3);
                    throw msg;
                }
                const resourceName = resource;
                const urls = {
                    "write-access-status": "/rw/controlstation/writeaccess/status",
                    "release-appeal-counter": "/rw/controlstation/writeaccess/release/appeal",
                    "tpu-safety-protocol-connected": "/rw/controlstation/tpu/safety/protocol/status",
                    "local-is-connected": "/rw/controlstation/local/isconnected"
                };
                const callbacks = [];
                const raiseEvent = async () => {
                    let parsedValue;
                    try {
                        switch (resourceName) {
                          case "write-access-status":
                            parsedValue = await o.ControlStation.getWriteAccessStatus();
                            break;

                          case "release-appeal-counter":
                            parsedValue = await o.ControlStation.getWriteAccessReleaseAppealChangeCounter();
                            break;

                          case "tpu-safety-protocol-connected":
                            parsedValue = await o.ControlStation.getTPUSafetyProtocolStatus();
                            break;

                          case "local-is-connected":
                            parsedValue = await o.ControlStation.isLocalConnected();
                            break;

                          default:
                            o.writeDebug(`ControlStation.Monitor.onchanged: Unknown resource: ${resourceName}`, 3);
                        }
                    } catch (error) {
                        o.writeDebug(`ControlStation.Monitor.raiseEvent: Error fetching resource ${resourceName}. >>> ${error.toString()}`, 3);
                    }
                    for (const cb of callbacks) {
                        try {
                            cb(parsedValue);
                        } catch (error) {
                            o.writeDebug(`ControlStation.Monitor callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                this.onchanged = newValue => {
                    let parsedValue;
                    switch (resourceName) {
                      case "write-access-status":
                        parsedValue = {
                            name: newValue["control-station-name"],
                            id: newValue["control-station-Id"],
                            externalControlEnabled: newValue["external-control-Enabled"] === "true",
                            status: newValue["write-access-held"] === "true"
                        };
                        break;

                      case "release-appeal-counter":
                        parsedValue = Number.parseInt(newValue["change-count"]);
                        break;

                      case "tpu-safety-protocol-connected":
                        parsedValue = newValue["IsConnected"] === "true";
                        break;

                      case "local-is-connected":
                        parsedValue = newValue["IsConnected"] === "true";
                        break;

                      default:
                        o.writeDebug(`ControlStation.Monitor.onchanged: Unknown resource: ${resourceName}`, 3);
                    }
                    for (const cb of callbacks) {
                        try {
                            cb(parsedValue);
                        } catch (error) {
                            o.writeDebug(`ControlStation.Monitor callback failed. >>> ${error.toString()}`, 3);
                        }
                    }
                };
                this.getTitle = () => {
                    return urls[resourceName];
                };
                this.getResourceString = () => {
                    return this.getTitle();
                };
                this.addCallbackOnChanged = function(callback) {
                    if (typeof callback !== "function") throw new Error("Callback is not a valid function.");
                    callbacks.push(callback);
                };
                this.subscribe = async (raiseInitial = false) => {
                    await checkSpoc();
                    if (raiseInitial === true) {
                        await o.Subscriptions.subscribe([ this ], raiseEvent);
                    } else {
                        await o.Subscriptions.subscribe([ this ]);
                    }
                };
            }
            this.getMonitor = function(resource) {
                return new Monitor(resource);
            };
            this.registerAsLocal = async key => {
                await checkSpoc();
                checkNotTPU();
                try {
                    await o.Network.post("/rw/controlstation/register/local", `local-presence-key=${encodeURIComponent(key)}`);
                } catch (error) {
                    throw createStatusObject("Could not register as local control station.", error);
                }
            };
            this.registerAsRemote = async (controlStationName = null, controlStationId = null, pincode = null, autoReleaseWriteAccess = true) => {
                await checkSpoc();
                checkNotTPU();
                if (controlStationName === null) {
                    controlStationName = `Web client (App SDK ${o.RWS_LIB_VERSION})`;
                }
                if (controlStationId === null) {
                    controlStationId = `{${crypto.randomUUID()}}`;
                }
                if (pincode === null) {
                    const buf = new Uint32Array(1);
                    crypto.getRandomValues(buf);
                    pincode = buf[0].toString();
                }
                let body = `control-station-name=${encodeURIComponent(controlStationName)}&control-station-id=${encodeURIComponent(controlStationId)}&pincode=${encodeURIComponent(pincode)}&release-write-access-when-lost=${autoReleaseWriteAccess ? "true" : "false"}`;
                try {
                    await o.Network.post("/rw/controlstation/register/remote", body);
                } catch (error) {
                    throw createStatusObject("Could not register as remote control station.", error);
                }
                currentRemoteId = controlStationId;
            };
            this.requestWriteAccess = async () => {
                await checkSpoc();
                checkNotTPU();
                try {
                    await o.Network.post("/rw/controlstation/writeaccess/request");
                } catch (error) {
                    throw createStatusObject("Could not acquire write access.", error);
                }
            };
            this.releaseWriteAccess = async () => {
                await checkSpoc();
                checkNotTPU();
                try {
                    await o.Network.post("/rw/controlstation/writeaccess/release");
                } catch (error) {
                    throw createStatusObject("Could not release write access.", error);
                }
            };
            this.disableExternalControl = async () => {
                await checkSpoc();
                checkNotTPU();
                try {
                    await o.Network.post("/rw/controlstation/disableexternalcontrol");
                } catch (error) {
                    throw createStatusObject("Could not disable external control.", error);
                }
            };
            this.allowMotionControl = async (allow = true) => {
                await checkSpoc();
                checkNotTPU();
                try {
                    await o.Network.post("/rw/controlstation/allowmotioncontrol", `allow-motion-control=${encodeURIComponent(allow ? "true" : "false")}`);
                } catch (error) {
                    throw createStatusObject("Could not allow motion control.", error);
                }
            };
            this.isMotionControlAllowed = async () => {
                await checkSpoc();
                let resp;
                try {
                    resp = JSON.parse((await o.Network.get("/rw/controlstation/allowmotioncontrol")).response).state[0]["is-enabled"] === "true";
                } catch (error) {
                    throw createStatusObject("Could not check if motion control is allowed.", error);
                }
                return resp;
            };
            this.getType = async () => {
                await checkSpoc();
                let resp;
                let val;
                try {
                    resp = JSON.parse((await o.Network.get("/rw/controlstation/type")).response).state[0]["control-station-type"];
                    val = this.ControlStationType[resp];
                    if (val === undefined) {
                        throw "Unknown control station type received: " + resp;
                    }
                } catch (error) {
                    throw createStatusObject("Could not get registered control station type.", error);
                }
                return val;
            };
            this.isLocalConnected = async () => {
                await checkSpoc();
                let resp;
                try {
                    resp = JSON.parse((await o.Network.get("/rw/controlstation/local/isconnected")).response).state[0]["control-station-local-isconnected"] === "true";
                } catch (error) {
                    throw createStatusObject("Could not check if local control station is connected.", error);
                }
                return resp;
            };
            this.writeAccessReleaseAppeal = async () => {
                await checkSpoc();
                checkNotTPU();
                try {
                    await o.Network.post("/rw/controlstation/writeaccess/release/appeal");
                } catch (error) {
                    throw createStatusObject("Could not appeal write access release.", error);
                }
            };
            this.getWriteAccessStatus = async () => {
                await checkSpoc();
                let resp = {};
                try {
                    const rwsResp = JSON.parse((await o.Network.get("/rw/controlstation/writeaccess/status")).response).state[0];
                    resp.name = rwsResp["held-by-control-station-name"];
                    resp.id = rwsResp["held-by-control-station-Id"];
                    resp.externalControlEnabled = rwsResp["control-station-external-control-enabled"] === "true";
                    resp.status = rwsResp["control-station-write-access-held"] === "true";
                } catch (error) {
                    throw createStatusObject("Could not get write access status.", error);
                }
                return resp;
            };
            this.getWriteAccessReleaseAppealChangeCounter = async () => {
                await checkSpoc();
                checkNotTPU();
                let resp;
                try {
                    resp = Number.parseInt(JSON.parse((await o.Network.get("/rw/controlstation/writeaccess/release/appeal/changecount")).response).state[0]["changecount"]);
                } catch (error) {
                    throw createStatusObject("Could not get write access release appeal change counter.", error);
                }
                return resp;
            };
            this.getTPUSafetyProtocolStatus = async () => {
                await checkSpoc();
                let resp;
                try {
                    resp = JSON.parse((await o.Network.get("/rw/controlstation/tpu/safety/protocol/status")).response).state[0]["is-connected"] === "true";
                } catch (error) {
                    throw createStatusObject("Could not get TPU safety protocol status.", error);
                }
                return resp;
            };
            this.getId = async () => {
                await checkSpoc();
                let resp;
                try {
                    resp = JSON.parse((await o.Network.get("/rw/controlstation/id")).response).state[0]["control-station-Id"];
                } catch (error) {
                    throw createStatusObject("Could not get control station Id", error);
                }
                return resp;
            };
        }();
        o.Network = new function() {
            this.setCookies = data => {
                let cookies = JSON.parse(data).cookies;
                let index = 0;
                while ((index = cookies.indexOf(";")) != -1) {
                    let cookie = cookies.substr(0, index);
                    document.cookie = cookie;
                    if (cookies.length < index + 3) break;
                    cookies = cookies.substr(index + 2);
                }
                return "Cookies updated!";
            };
            this.heartBeat = () => {
                this.get("/").then(msg => {}, error => o.writeDebug(`Heartbeat Failed.  >>>  ${error.httpStatus.code} ${error.httpStatus.text}`, 3));
                setTimeout(this.heartBeat, 3e4);
            };
            this.send = (method, path, requestHeaders = {}, body = null) => {
                return new Promise((resolve, reject) => {
                    let req = new XMLHttpRequest();
                    if (o.__unload !== true) {
                        req.timeout = HTTP_REQUEST_TIMEOUT;
                    }
                    req.ontimeout = () => {
                        o.writeDebug("Request timed out.", 2);
                        reject("RWS request timed out.");
                    };
                    req.onerror = () => {
                        o.writeDebug(`Send error. ${method + " " + path}`, 2);
                        reject("Send error.");
                    };
                    req.onreadystatechange = () => {
                        if (req.readyState === 4) {
                            if (req.status === 0) return;
                            if (Math.floor(req.status / 100) !== 2) {
                                let r = {
                                    message: "",
                                    httpStatus: {
                                        code: req.status,
                                        text: req.statusText
                                    }
                                };
                                if (req.responseText !== null && req.responseText !== "") {
                                    return verfifyErrorCode(req.responseText).then(x => {
                                        let call = body === null ? path : `${path} ${body}`;
                                        if (x.severity.toLowerCase() === "error") {
                                            o.writeDebug(`RWS call '${call}', ${x.severity}: ${x.name}, '${x.description}'`, 1);
                                        }
                                        r.controllerStatus = x;
                                        return reject(r);
                                    }).catch(() => reject(r));
                                }
                                return reject(r);
                            } else {
                                if (path === "/") {
                                    resolve(req);
                                    return;
                                }
                                if (req.responseText === null || req.responseText === "") return resolve(req);
                                if (req.getResponseHeader("Content-Type") !== "application/hal+json;v=2.0") return resolve(req);
                                let json = parseJSON(req.responseText);
                                if (json === undefined) return resolve(req);
                                return verifyReturnCode(json).then(() => resolve(req)).catch(errors => {
                                    let s = body === null ? path : `${path} ${body}`;
                                    for (let item in errors) {
                                        if (errors[item].severity.toLowerCase() === "error") {
                                            o.writeDebug(`RWS call '${s}', ${errors[item].severity}: '${item}' - ${errors[item].name}, '${errors[item].description}'`, 1);
                                        }
                                    }
                                    resolve(req);
                                    return;
                                });
                            }
                        }
                    };
                    try {
                        req.open(method, path, o.__unload === true ? false : true);
                        for (var key in requestHeaders) {
                            var value = requestHeaders[key];
                            req.setRequestHeader(key, value);
                        }
                        if (body !== null) req.send(body); else req.send();
                    } catch (exception) {
                        reject("Error during communication with RWS! Exception: " + exception.message);
                        return;
                    }
                }).catch(err => Promise.reject(err));
            };
            this.get = (path, additionalRequestHeaders = {}) => {
                return this.send("GET", path, Object.assign({
                    Accept: "application/hal+json;v=2.0"
                }, additionalRequestHeaders));
            };
            this.post = (path, body, additionalRequestHeaders = {}) => {
                return this.send("POST", path, Object.assign({
                    "Content-Type": "application/x-www-form-urlencoded;v=2.0",
                    Accept: "application/hal+json;v=2.0"
                }, additionalRequestHeaders), body);
            };
            this.put = (path, body, additionalRequestHeaders = {}) => {
                return this.send("PUT", path, Object.assign({
                    "Content-Type": "application/x-www-form-urlencoded;v=2.0"
                }, additionalRequestHeaders), body);
            };
            this.delete = (path, additionalRequestHeaders = {}) => {
                return this.send("DELETE", path, Object.assign({
                    Accept: "application/hal+json;v=2.0"
                }, additionalRequestHeaders));
            };
            this.options = (path, additionalRequestHeaders = {}) => {
                return this.send("OPTIONS", path, Object.assign({
                    Accept: "application/xhtml+xml;v=2.0"
                }, additionalRequestHeaders));
            };
            this.head = (path, additionalRequestHeaders = {}) => {
                return this.send("HEAD", path, Object.assign({
                    Accept: "application/xhtml+xml;v=2.0"
                }, additionalRequestHeaders));
            };
        }();
        o.constructedMain = true;
    })(RWS);
    window["_onMastershipRequested"] = RWS.Mastership.onRequested;
    window["_onMastershipReleased"] = RWS.Mastership.onReleased;
    window["_onMotionMastershipRequested"] = RWS.MotionMastership.onRequested;
    window["_onMotionMastershipReleased"] = RWS.MotionMastership.onReleased;
    window["_setCookies"] = RWS.Network.setCookies;
}

if (typeof RWS.constructedRapidData === "undefined") {
    (function(rd) {
        rd.RAPIDDATA_LIB_VERSION = "1.6.0";
        let monitor = null;
        rd.initCache = () => {
            rd.resetSymbolTypeCache();
            monitor = new Monitor();
        };
        window.addEventListener("load", rd.initCache, false);
        function Monitor() {
            let taskChangeMonitors = [];
            let excStateMonitors = [];
            let blockClear = false;
            let tasks = [];
            (async function() {
                tasks = await RWS.Rapid.getTasks();
                for (let iii = 0; iii < tasks.length; iii++) {
                    let props = await tasks[iii].getProperties();
                    if (props.type !== "normal") continue;
                    let name = tasks[iii].getName();
                    let taskChange = new TaskChangeMonitor(name);
                    let excState = new ExcStateMonitor(name);
                    taskChangeMonitors.push(taskChange);
                    excStateMonitors.push(excState);
                }
            })();
            function TaskChangeMonitor(task) {
                let resourceString = `/rw/rapid/tasks/${encodeURIComponent(task)};taskchange`;
                let resourceUrl = `/rw/rapid/tasks/${encodeURIComponent(task)}`;
                this.getTitle = function() {
                    return resourceUrl;
                };
                this.getResourceString = function() {
                    return resourceString;
                };
                this.onchanged = function(newValue) {
                    if (blockClear === true) {
                        blockClear = false;
                        return;
                    }
                    if (newValue.hasOwnProperty("task-name") && newValue["task-name"] === task) {
                        RWS.removeSymbolTypes(task);
                    }
                };
                RWS.Subscriptions.subscribe([ this ]).catch(() => RWS.writeDebug(`Failed to subscribe to task changes for '${task}'.`, 2));
            }
            function ExcStateMonitor(task) {
                let resourceString = `/rw/rapid/tasks/${encodeURIComponent(task)};excstate`;
                let resourceUrl = `/rw/rapid/tasks/${encodeURIComponent(task)}`;
                this.getTitle = function() {
                    return resourceUrl;
                };
                this.getResourceString = function() {
                    return resourceString;
                };
                this.onchanged = function(newValue) {
                    if (newValue.hasOwnProperty("task-name") && newValue["task-name"] === task) {
                        let state = newValue.hasOwnProperty("pgmtaskexec-state") ? newValue["pgmtaskexec-state"] : "";
                        if (state === "started") blockClear = true;
                    }
                };
                RWS.Subscriptions.subscribe([ this ]).catch(() => RWS.writeDebug("Failed to subscribe to execution state changes.", 2));
            }
        }
        function getEmptyDataType() {
            return {
                type: "",
                url: "",
                isAtomic: false,
                isArray: false,
                dimensions: [],
                isAlias: false,
                aliasTypeUrl: "",
                isRecord: false,
                numberOfComponents: 0,
                components: []
            };
        }
        function deepCopy(original) {
            if (Array.isArray(original)) {
                let ret = [];
                for (let item of original) {
                    ret.push(deepCopy(item));
                }
                return ret;
            }
            if (typeof original == "object" && original !== null) {
                let ret = {};
                for (let key of Object.keys(original)) {
                    ret[key] = deepCopy(original[key]);
                }
                return ret;
            }
            return original;
        }
        let symbolTypeCache = {};
        rd.resetSymbolTypeCache = function() {
            symbolTypeCache = {};
            symbolTypeCache["RAPID/num"] = getEmptyDataType();
            symbolTypeCache["RAPID/num"]["type"] = "num";
            symbolTypeCache["RAPID/num"]["url"] = "RAPID/num";
            symbolTypeCache["RAPID/num"]["isAtomic"] = true;
            symbolTypeCache["RAPID/dnum"] = getEmptyDataType();
            symbolTypeCache["RAPID/dnum"]["type"] = "dnum";
            symbolTypeCache["RAPID/dnum"]["url"] = "RAPID/dnum";
            symbolTypeCache["RAPID/dnum"]["isAtomic"] = true;
            symbolTypeCache["RAPID/string"] = getEmptyDataType();
            symbolTypeCache["RAPID/string"]["type"] = "string";
            symbolTypeCache["RAPID/string"]["url"] = "RAPID/string";
            symbolTypeCache["RAPID/string"]["isAtomic"] = true;
            symbolTypeCache["RAPID/bool"] = getEmptyDataType();
            symbolTypeCache["RAPID/bool"]["type"] = "bool";
            symbolTypeCache["RAPID/bool"]["url"] = "RAPID/bool";
            symbolTypeCache["RAPID/bool"]["isAtomic"] = true;
            symbolTypeCache["RAPID/btnres"] = getEmptyDataType();
            symbolTypeCache["RAPID/btnres"]["type"] = "btnres";
            symbolTypeCache["RAPID/btnres"]["url"] = "RAPID/btnres";
            symbolTypeCache["RAPID/btnres"]["isAlias"] = true;
            symbolTypeCache["RAPID/btnres"]["aliasTypeUrl"] = "RAPID/num";
            symbolTypeCache["RAPID/robjoint"] = getEmptyDataType();
            symbolTypeCache["RAPID/robjoint"]["type"] = "robjoint";
            symbolTypeCache["RAPID/robjoint"]["url"] = "RAPID/robjoint";
            symbolTypeCache["RAPID/robjoint"]["isRecord"] = true;
            symbolTypeCache["RAPID/robjoint"]["numberOfComponents"] = 6;
            symbolTypeCache["RAPID/robjoint"]["components"] = [];
            symbolTypeCache["RAPID/robjoint"]["components"].push({
                name: "rax_1",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/robjoint"]["components"].push({
                name: "rax_2",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/robjoint"]["components"].push({
                name: "rax_3",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/robjoint"]["components"].push({
                name: "rax_4",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/robjoint"]["components"].push({
                name: "rax_5",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/robjoint"]["components"].push({
                name: "rax_6",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/extjoint"] = getEmptyDataType();
            symbolTypeCache["RAPID/extjoint"]["type"] = "extjoint";
            symbolTypeCache["RAPID/extjoint"]["url"] = "RAPID/extjoint";
            symbolTypeCache["RAPID/extjoint"]["isRecord"] = true;
            symbolTypeCache["RAPID/extjoint"]["numberOfComponents"] = 6;
            symbolTypeCache["RAPID/extjoint"]["components"] = [];
            symbolTypeCache["RAPID/extjoint"]["components"].push({
                name: "eax_a",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/extjoint"]["components"].push({
                name: "eax_b",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/extjoint"]["components"].push({
                name: "eax_c",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/extjoint"]["components"].push({
                name: "eax_d",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/extjoint"]["components"].push({
                name: "eax_e",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/extjoint"]["components"].push({
                name: "eax_f",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/jointtarget"] = getEmptyDataType();
            symbolTypeCache["RAPID/jointtarget"]["type"] = "jointtarget";
            symbolTypeCache["RAPID/jointtarget"]["url"] = "RAPID/jointtarget";
            symbolTypeCache["RAPID/jointtarget"]["isRecord"] = true;
            symbolTypeCache["RAPID/jointtarget"]["numberOfComponents"] = 2;
            symbolTypeCache["RAPID/jointtarget"]["components"] = [];
            symbolTypeCache["RAPID/jointtarget"]["components"].push({
                name: "robax",
                type: symbolTypeCache["RAPID/robjoint"]
            });
            symbolTypeCache["RAPID/jointtarget"]["components"].push({
                name: "extax",
                type: symbolTypeCache["RAPID/extjoint"]
            });
            symbolTypeCache["RAPID/pos"] = getEmptyDataType();
            symbolTypeCache["RAPID/pos"]["type"] = "pos";
            symbolTypeCache["RAPID/pos"]["url"] = "RAPID/pos";
            symbolTypeCache["RAPID/pos"]["isRecord"] = true;
            symbolTypeCache["RAPID/pos"]["numberOfComponents"] = 3;
            symbolTypeCache["RAPID/pos"]["components"] = [];
            symbolTypeCache["RAPID/pos"]["components"].push({
                name: "x",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/pos"]["components"].push({
                name: "y",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/pos"]["components"].push({
                name: "z",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/orient"] = getEmptyDataType();
            symbolTypeCache["RAPID/orient"]["type"] = "orient";
            symbolTypeCache["RAPID/orient"]["url"] = "RAPID/orient";
            symbolTypeCache["RAPID/orient"]["isRecord"] = true;
            symbolTypeCache["RAPID/orient"]["numberOfComponents"] = 4;
            symbolTypeCache["RAPID/orient"]["components"] = [];
            symbolTypeCache["RAPID/orient"]["components"].push({
                name: "q1",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/orient"]["components"].push({
                name: "q2",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/orient"]["components"].push({
                name: "q3",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/orient"]["components"].push({
                name: "q4",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/pose"] = getEmptyDataType();
            symbolTypeCache["RAPID/pose"]["type"] = "pose";
            symbolTypeCache["RAPID/pose"]["url"] = "RAPID/pose";
            symbolTypeCache["RAPID/pose"]["isRecord"] = true;
            symbolTypeCache["RAPID/pose"]["numberOfComponents"] = 2;
            symbolTypeCache["RAPID/pose"]["components"] = [];
            symbolTypeCache["RAPID/pose"]["components"].push({
                name: "trans",
                type: symbolTypeCache["RAPID/pos"]
            });
            symbolTypeCache["RAPID/pose"]["components"].push({
                name: "rot",
                type: symbolTypeCache["RAPID/orient"]
            });
            symbolTypeCache["RAPID/confdata"] = getEmptyDataType();
            symbolTypeCache["RAPID/confdata"]["type"] = "confdata";
            symbolTypeCache["RAPID/confdata"]["url"] = "RAPID/confdata";
            symbolTypeCache["RAPID/confdata"]["isRecord"] = true;
            symbolTypeCache["RAPID/confdata"]["numberOfComponents"] = 4;
            symbolTypeCache["RAPID/confdata"]["components"] = [];
            symbolTypeCache["RAPID/confdata"]["components"].push({
                name: "cf1",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/confdata"]["components"].push({
                name: "cf4",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/confdata"]["components"].push({
                name: "cf6",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/confdata"]["components"].push({
                name: "cfx",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/robtarget"] = getEmptyDataType();
            symbolTypeCache["RAPID/robtarget"]["type"] = "robtarget";
            symbolTypeCache["RAPID/robtarget"]["url"] = "RAPID/robtarget";
            symbolTypeCache["RAPID/robtarget"]["isRecord"] = true;
            symbolTypeCache["RAPID/robtarget"]["numberOfComponents"] = 4;
            symbolTypeCache["RAPID/robtarget"]["components"] = [];
            symbolTypeCache["RAPID/robtarget"]["components"].push({
                name: "trans",
                type: symbolTypeCache["RAPID/pos"]
            });
            symbolTypeCache["RAPID/robtarget"]["components"].push({
                name: "rot",
                type: symbolTypeCache["RAPID/orient"]
            });
            symbolTypeCache["RAPID/robtarget"]["components"].push({
                name: "robconf",
                type: symbolTypeCache["RAPID/confdata"]
            });
            symbolTypeCache["RAPID/robtarget"]["components"].push({
                name: "extax",
                type: symbolTypeCache["RAPID/extjoint"]
            });
            symbolTypeCache["RAPID/zonedata"] = getEmptyDataType();
            symbolTypeCache["RAPID/zonedata"]["type"] = "zonedata";
            symbolTypeCache["RAPID/zonedata"]["url"] = "RAPID/zonedata";
            symbolTypeCache["RAPID/zonedata"]["isRecord"] = true;
            symbolTypeCache["RAPID/zonedata"]["numberOfComponents"] = 7;
            symbolTypeCache["RAPID/zonedata"]["components"] = [];
            symbolTypeCache["RAPID/zonedata"]["components"].push({
                name: "finep",
                type: symbolTypeCache["RAPID/bool"]
            });
            symbolTypeCache["RAPID/zonedata"]["components"].push({
                name: "pzone_tcp",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/zonedata"]["components"].push({
                name: "pzone_ori",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/zonedata"]["components"].push({
                name: "pzone_eax",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/zonedata"]["components"].push({
                name: "zone_ori",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/zonedata"]["components"].push({
                name: "zone_leax",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/zonedata"]["components"].push({
                name: "zone_reax",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/wobjdata"] = getEmptyDataType();
            symbolTypeCache["RAPID/wobjdata"]["type"] = "wobjdata";
            symbolTypeCache["RAPID/wobjdata"]["url"] = "RAPID/wobjdata";
            symbolTypeCache["RAPID/wobjdata"]["isRecord"] = true;
            symbolTypeCache["RAPID/wobjdata"]["numberOfComponents"] = 5;
            symbolTypeCache["RAPID/wobjdata"]["components"] = [];
            symbolTypeCache["RAPID/wobjdata"]["components"].push({
                name: "robhold",
                type: symbolTypeCache["RAPID/bool"]
            });
            symbolTypeCache["RAPID/wobjdata"]["components"].push({
                name: "ufprog",
                type: symbolTypeCache["RAPID/bool"]
            });
            symbolTypeCache["RAPID/wobjdata"]["components"].push({
                name: "ufmec",
                type: symbolTypeCache["RAPID/string"]
            });
            symbolTypeCache["RAPID/wobjdata"]["components"].push({
                name: "uframe",
                type: symbolTypeCache["RAPID/pose"]
            });
            symbolTypeCache["RAPID/wobjdata"]["components"].push({
                name: "oframe",
                type: symbolTypeCache["RAPID/pose"]
            });
            symbolTypeCache["RAPID/loaddata"] = getEmptyDataType();
            symbolTypeCache["RAPID/loaddata"]["type"] = "loaddata";
            symbolTypeCache["RAPID/loaddata"]["url"] = "RAPID/loaddata";
            symbolTypeCache["RAPID/loaddata"]["isRecord"] = true;
            symbolTypeCache["RAPID/loaddata"]["numberOfComponents"] = 6;
            symbolTypeCache["RAPID/loaddata"]["components"] = [];
            symbolTypeCache["RAPID/loaddata"]["components"].push({
                name: "mass",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/loaddata"]["components"].push({
                name: "cog",
                type: symbolTypeCache["RAPID/pos"]
            });
            symbolTypeCache["RAPID/loaddata"]["components"].push({
                name: "aom",
                type: symbolTypeCache["RAPID/orient"]
            });
            symbolTypeCache["RAPID/loaddata"]["components"].push({
                name: "ix",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/loaddata"]["components"].push({
                name: "iy",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/loaddata"]["components"].push({
                name: "iz",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/tooldata"] = getEmptyDataType();
            symbolTypeCache["RAPID/tooldata"]["type"] = "tooldata";
            symbolTypeCache["RAPID/tooldata"]["url"] = "RAPID/tooldata";
            symbolTypeCache["RAPID/tooldata"]["isRecord"] = true;
            symbolTypeCache["RAPID/tooldata"]["numberOfComponents"] = 3;
            symbolTypeCache["RAPID/tooldata"]["components"] = [];
            symbolTypeCache["RAPID/tooldata"]["components"].push({
                name: "robhold",
                type: symbolTypeCache["RAPID/bool"]
            });
            symbolTypeCache["RAPID/tooldata"]["components"].push({
                name: "tframe",
                type: symbolTypeCache["RAPID/pose"]
            });
            symbolTypeCache["RAPID/tooldata"]["components"].push({
                name: "tload",
                type: symbolTypeCache["RAPID/loaddata"]
            });
            symbolTypeCache["RAPID/speeddata"] = getEmptyDataType();
            symbolTypeCache["RAPID/speeddata"]["type"] = "speeddata";
            symbolTypeCache["RAPID/speeddata"]["url"] = "RAPID/speeddata";
            symbolTypeCache["RAPID/speeddata"]["isRecord"] = true;
            symbolTypeCache["RAPID/speeddata"]["numberOfComponents"] = 4;
            symbolTypeCache["RAPID/speeddata"]["components"] = [];
            symbolTypeCache["RAPID/speeddata"]["components"].push({
                name: "v_tcp",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/speeddata"]["components"].push({
                name: "v_ori",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/speeddata"]["components"].push({
                name: "v_leax",
                type: symbolTypeCache["RAPID/num"]
            });
            symbolTypeCache["RAPID/speeddata"]["components"].push({
                name: "v_reax",
                type: symbolTypeCache["RAPID/num"]
            });
        };
        rd.removeSymbolTypes = function(task, module = "") {
            let symbolUrl = `RAPID/${task}/`;
            if (typeof module === "string" && module !== "") symbolUrl += module;
            let newDictionary = {};
            for (let item in symbolTypeCache) {
                if (item.startsWith(symbolUrl) == false) {
                    newDictionary[item] = symbolTypeCache[item];
                }
            }
            symbolTypeCache = newDictionary;
        };
        rd.getCachedSymbolTypeNames = function() {
            let keys = Object.keys(symbolTypeCache);
            return keys;
        };
        rd.getCachedSymbolType = function(type) {
            if (typeof symbolTypeCache[type] !== "undefined") return symbolTypeCache[type];
            return undefined;
        };
        rd.RapidData = new function() {
            this.Type = new function() {
                this.getType = function(rapidData) {
                    if (typeof rapidData.getDataType === "undefined") {
                        RWS.writeDebug("rapidData is not a valid Data object", 3);
                        return Promise.reject("rapidData is not a valid Data object");
                    }
                    return processData(rapidData);
                };
                function parseJSON(json) {
                    try {
                        return JSON.parse(json);
                    } catch (error) {
                        return undefined;
                    }
                }
                function copyProperties(fromObject) {
                    if (fromObject instanceof Object) {
                        let toObject = getEmptyDataType();
                        for (const property in fromObject) {
                            if (fromObject.hasOwnProperty(property)) {
                                if (Array.isArray(fromObject[property])) {
                                    toObject[property] = [];
                                    for (let iii = 0; iii < fromObject[property].length; iii++) {
                                        if (typeof fromObject[property][iii] === "number") {
                                            toObject[property].push(fromObject[property][iii]);
                                        } else {
                                            let dt = copyProperties(fromObject[property][iii]);
                                            toObject[property].push(dt);
                                        }
                                    }
                                } else {
                                    toObject[property] = fromObject[property];
                                }
                            }
                        }
                        return toObject;
                    } else {
                        throw new Error("Not a supported datatype.");
                    }
                }
                function processData(data) {
                    return getProperties(data.getTitle()).then(item => {
                        let datatype = processDataType(item);
                        return Promise.resolve(datatype);
                    }).catch(err => Promise.reject(`Failed to parse data. >>> ${err}`));
                }
                async function processDataType(item) {
                    let datatype = getEmptyDataType();
                    if (symbolTypeCache.hasOwnProperty(item.symburl)) {
                        datatype = copyProperties(symbolTypeCache[item.symburl]);
                        return datatype;
                    }
                    switch (item.symtyp) {
                      case "atm":
                        datatype["isAtomic"] = true;
                        datatype["type"] = item.name;
                        datatype["url"] = item.symburl;
                        symbolTypeCache[item.symburl] = copyProperties(datatype);
                        break;

                      case "con":
                      case "var":
                      case "per":
                        let subitem1 = await getProperties(item.typurl);
                        datatype = await processDataType(subitem1);
                        datatype["type"] = item.dattyp;
                        datatype["url"] = item.symburl;
                        datatype["isArray"] = item.ndim !== "0";
                        if (datatype["isArray"] === true) {
                            datatype["dimensions"] = [];
                            let splits = item.dim.trim().split(" ");
                            for (const s of splits) {
                                datatype["dimensions"].push(parseInt(s));
                            }
                        }
                        symbolTypeCache[item.symburl] = copyProperties(datatype);
                        break;

                      case "ali":
                        datatype["type"] = item.name;
                        datatype["isAlias"] = true;
                        datatype["aliasTypeUrl"] = item.typurl;
                        if (symbolTypeCache.hasOwnProperty(item.typurl) === false) {
                            let subitem2 = await getProperties(item.typurl);
                            await processDataType(subitem2);
                        }
                        datatype["url"] = item.symburl;
                        symbolTypeCache[item.symburl] = copyProperties(datatype);
                        break;

                      case "rcp":
                        let subitem3 = await getProperties(item.typurl);
                        datatype = await processDataType(subitem3);
                        datatype["type"] = item.dattyp;
                        datatype["url"] = item.symburl;
                        symbolTypeCache[item.symburl] = copyProperties(datatype);
                        break;

                      case "rec":
                        datatype["type"] = item.name;
                        datatype["isRecord"] = true;
                        datatype["numberOfComponents"] = parseInt(item.ncom);
                        try {
                            let x1 = await getRecordComponents(item.symburl);
                            datatype["components"] = x1;
                        } catch (err) {
                            console.warn(err);
                        }
                        datatype["url"] = item.symburl;
                        symbolTypeCache[item.symburl] = copyProperties(datatype);
                        break;

                      default:
                        datatype["type"] = "unknown";
                    }
                    return datatype;
                }
                function getProperties(symbolUrl) {
                    let url = "/rw/rapid/symbol/" + encodeURIComponent(symbolUrl) + "/properties";
                    return RWS.Network.get(url).then(x1 => {
                        let obj = parseJSON(x1.responseText);
                        if (obj.hasOwnProperty("_embedded")) {
                            for (const item of obj._embedded.resources) {
                                switch (item._type) {
                                  case "rap-sympropconstant":
                                  case "rap-sympropvar":
                                  case "rap-symproppers":
                                  case "rap-sympropalias":
                                  case "rap-symproprecord":
                                  case "rap-sympropreccomp-li":
                                  case "rap-sympropatomic":
                                    return Promise.resolve(item);

                                  default:
                                    continue;
                                }
                            }
                        } else if (obj.hasOwnProperty("state")) {
                            for (const item of obj.state) {
                                switch (item._type) {
                                  case "rap-sympropconstant":
                                  case "rap-sympropvar":
                                  case "rap-symproppers":
                                  case "rap-sympropalias":
                                  case "rap-symproprecord":
                                  case "rap-sympropreccomp-li":
                                  case "rap-sympropatomic":
                                    return Promise.resolve(item);

                                  default:
                                    continue;
                                }
                            }
                        }
                        return Promise.reject("No valid datatype found.");
                    }).catch(x2 => Promise.reject(x2));
                }
                async function getRecordComponents(symbolUrl) {
                    const doSearch = (url, body, symbols) => {
                        if (url === "") return Promise.resolve(symbols);
                        return RWS.Network.post(url, body).then(async res => {
                            let obj = null;
                            try {
                                obj = JSON.parse(res.responseText);
                            } catch (error) {
                                return Promise.reject("Could not parse JSON response from RWS");
                            }
                            if (obj._links.hasOwnProperty("next")) {
                                url = "/rw/rapid/" + obj._links["next"].href;
                            } else {
                                url = "";
                            }
                            if (obj.hasOwnProperty("_embedded") && obj["_embedded"].hasOwnProperty("resources")) {
                                for (const item of obj._embedded.resources) {
                                    if (item._type === "rap-sympropreccomp-li" && item.symburl.startsWith(symbolUrl + "/")) {
                                        symbols.push(item);
                                    }
                                }
                            }
                            return doSearch(url, body, symbols);
                        }).catch(err => Promise.reject(err));
                    };
                    let components = [];
                    try {
                        let url = "/rw/rapid/symbols/search";
                        let body = "";
                        let splits = symbolUrl.split("/");
                        if (splits.length <= 2) body = `view=block&blockurl=RAPID&symtyp=rcp&recursive=TRUE&skipshared=FALSE&onlyused=FALSE`; else body = `view=block&blockurl=${encodeURIComponent(symbolUrl)}&symtyp=rcp&recursive=FALSE&skipshared=FALSE&onlyused=FALSE`;
                        let items = await doSearch(url, body, []);
                        let temp = items.sort((x1, x2) => parseInt(x1.comnum) - parseInt(x2.comnum));
                        for (const item of temp) {
                            let subType = await processDataType(item);
                            components.push({
                                name: item.name,
                                type: subType
                            });
                        }
                    } catch (err) {
                        return Promise.reject(`Could not read record components >>> ${err}`);
                    }
                    return Promise.resolve(components);
                }
            }();
            this.Value = new function() {
                this.parseRawValue = function(rapidType, value) {
                    if (rapidType === null || typeof rapidType !== "object") {
                        let err = "rapidType is not a valid data type object";
                        RWS.writeDebug(err, 3);
                        return Promise.reject(err);
                    }
                    if (value === null || typeof value !== "string") {
                        let err = "value is not a valid string";
                        RWS.writeDebug(err, 3);
                        return Promise.reject(err);
                    }
                    return parseData(rapidType, value);
                };
                async function parseData(rapidType, dataValue) {
                    try {
                        let aliasType = {};
                        if (rapidType.isAlias) {
                            if (symbolTypeCache.hasOwnProperty(rapidType.aliasTypeUrl)) {
                                aliasType = symbolTypeCache[rapidType.aliasTypeUrl];
                            } else {
                                return Promise.reject("Could not parse data. Illegal alias value.");
                            }
                        }
                        if (rapidType.isArray) {
                            let tempType = deepCopy(rapidType);
                            if (rapidType.isAlias) {
                                tempType.isAlias = false;
                                tempType.aliasTypeUrl = "";
                                tempType.isAtomic = aliasType.isAtomic;
                                tempType.type = aliasType.type;
                                tempType.isRecord = aliasType.isRecord;
                                if (tempType.isRecord) {
                                    tempType.components = aliasType.components;
                                }
                            }
                            if (rapidType.dimensions.length === 1) {
                                return await parseArray(tempType, dataValue);
                            }
                            return await parseMatrix(tempType, dataValue);
                        }
                        if (rapidType.isRecord || rapidType.isAlias && aliasType.isRecord) {
                            let dataType = rapidType.isAlias ? aliasType : rapidType;
                            return await parseRecord(dataType, dataValue);
                        }
                        if (rapidType.isAtomic || rapidType.isAlias && aliasType.isAtomic) {
                            let dataType = rapidType.isAlias ? aliasType : rapidType;
                            switch (dataType.type) {
                              case "num":
                              case "dnum":
                                return Promise.resolve(parseFloat(dataValue));

                              case "string":
                                return Promise.resolve(RWS.RapidData.String.cleanupString(dataValue));

                              case "bool":
                                let b = dataValue.toUpperCase() == "TRUE";
                                return Promise.resolve(b);

                              default:
                                return Promise.reject("Could not parse data. Illegal atomic value.");
                            }
                        }
                        return Promise.reject("Unknown data type.");
                    } catch (err) {
                        return Promise.reject(`parseData failed >>> ${err}`);
                    }
                }
                async function parseArray(dataType, valueString) {
                    let s = valueString.replace(/^\[/g, "").replace(/\]$/g, "");
                    if (dataType.isRecord) {
                        let recordValues = await parseRecordArray(dataType, valueString.trim());
                        return Promise.resolve(recordValues);
                    }
                    if (dataType.isAtomic) {
                        switch (dataType.type) {
                          case "num":
                          case "dnum":
                            let numSplits = s.split(",");
                            let numValues = [];
                            for (const value of numSplits) {
                                numValues.push(parseFloat(value));
                            }
                            return Promise.resolve(numValues);

                          case "string":
                            let stringValues = await parseStringArray(valueString.trim());
                            return Promise.resolve(stringValues);

                          case "bool":
                            let boolSplits = s.split(",");
                            let boolValues = [];
                            for (const value of boolSplits) {
                                let b = value.toUpperCase() == "TRUE";
                                boolValues.push(b);
                            }
                            return Promise.resolve(boolValues);

                          default:
                            return Promise.reject("Could not parse data. Illegal array value.");
                        }
                    }
                }
                async function parseMatrix(dataType, valueString) {
                    if (dataType.isRecord) {
                        let matrixValues = await parseRecordMatrix(dataType, valueString.trim());
                        return Promise.resolve(matrixValues);
                    }
                    switch (dataType.type) {
                      case "num":
                      case "dnum":
                        let numValues = parseNumMatrix(valueString, dataType.dimensions);
                        return Promise.resolve(numValues);

                      case "string":
                        let stringValues = parseStringMatrix(valueString.trim(), dataType.dimensions);
                        return Promise.resolve(stringValues);

                      case "bool":
                        let boolValues = parseBoolMatrix(valueString, dataType.dimensions);
                        return Promise.resolve(boolValues);

                      default:
                        return Promise.reject("Could not parse data. Illegal array value.");
                    }
                }
                const groupObjects = (collection, count) => collection.reduce((acc, curr, idx) => (idx % count == 0 ? acc.push([ curr ]) : acc[acc.length - 1].push(curr)) && acc, []);
                function parseBoolMatrix(valueString, dimensions) {
                    let boolMatrix = valueString.replace(/\[/g, "").replace(/\]/g, "").split(",");
                    for (let iii = 0; iii < boolMatrix.length; iii++) {
                        boolMatrix[iii] = boolMatrix[iii].toUpperCase() == "TRUE";
                    }
                    for (let iii = dimensions.length; iii >= 1; iii--) {
                        boolMatrix = groupObjects(boolMatrix, dimensions[iii - 1]);
                    }
                    return boolMatrix[0];
                }
                function parseNumMatrix(valueString, dimensions) {
                    let numMatrix = valueString.replace(/\[/g, "").replace(/\]/g, "").split(",");
                    for (let iii = 0; iii < numMatrix.length; iii++) {
                        numMatrix[iii] = parseFloat(numMatrix[iii]);
                    }
                    for (let iii = dimensions.length; iii >= 1; iii--) {
                        numMatrix = groupObjects(numMatrix, dimensions[iii - 1]);
                    }
                    return numMatrix[0];
                }
                function parseStringMatrix(valueString, dimensions) {
                    let stringMatrix = parseStringArray(valueString);
                    for (let iii = dimensions.length; iii >= 1; iii--) {
                        stringMatrix = groupObjects(stringMatrix, dimensions[iii - 1]);
                    }
                    return stringMatrix[0];
                }
                function parseStringArray(valueString) {
                    let text = valueString.trim();
                    let extractedStrings = [];
                    let even = true;
                    let n = 0;
                    let start = -1;
                    while (n >= 0) {
                        n = text.indexOf('"', n);
                        if (n >= 0) {
                            if (start === -1) start = n;
                            even = even === false;
                            if (even === true && (text[n + 1] === "]" || text[n + 1] === ",")) {
                                let s = text.substring(start + 1, n);
                                extractedStrings.push(s);
                                start = -1;
                            }
                            n++;
                        }
                    }
                    return extractedStrings;
                }
                function getRandomString(length, text) {
                    const r = max => {
                        return Math.floor(Math.random() * Math.floor(max));
                    };
                    const x = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
                    let c = "";
                    for (let iii = 0; iii < length; iii++) c += x[r(x.length)];
                    if (text === null || text === "") return c;
                    while (text.includes(c) == true) {
                        for (let iii = 0; iii < length; iii++) c += x[r(x.length)];
                    }
                    return c;
                }
                async function getElements(valueString) {
                    try {
                        let rndStr = getRandomString(5, valueString);
                        const rndTemplate = index => {
                            return `${rndStr}_${index}_`;
                        };
                        let text = valueString.trim();
                        let replacedStrings = {};
                        let idx = 0;
                        let even = true;
                        let n = 0;
                        let start = -1;
                        while (n >= 0) {
                            n = text.indexOf('"', n);
                            if (n >= 0) {
                                if (start === -1) start = n;
                                even = even === false;
                                if (even === true && (text[n + 1] === "]" || text[n + 1] === ",")) {
                                    let s = text.substring(start, n + 1);
                                    let r = rndTemplate(idx++);
                                    replacedStrings[r] = s;
                                    text = text.replace(s, r);
                                    n += r.length - s.length;
                                    start = -1;
                                }
                                n++;
                            }
                        }
                        let components = text.replace(/\[/g, "").replace(/\]/g, "").split(",");
                        let retVal = {
                            components: components,
                            replacedStrings: replacedStrings
                        };
                        return Promise.resolve(retVal);
                    } catch (err) {
                        return Promise.reject(`getComponents failed >>> ${err}`);
                    }
                }
                async function parseRecordArray(dataType, valueString) {
                    try {
                        let elements = await getElements(valueString);
                        let array = [];
                        for (let iii = 0; iii < dataType.dimensions[0]; iii++) {
                            let record = {};
                            for (let jjj = 0; jjj < dataType.components.length; jjj++) {
                                record[dataType.components[jjj].name] = await parseComponentData(dataType.components[jjj].type, elements.components, elements.replacedStrings);
                            }
                            array.push(record);
                        }
                        return Promise.resolve(array);
                    } catch (err) {
                        return Promise.reject(`parseRecordArray failed >>> ${err}`);
                    }
                }
                async function parseRecordMatrix(dataType, valueString) {
                    try {
                        let elements = await getElements(valueString);
                        let count = 1;
                        for (let x1 = 0; x1 < dataType.dimensions.length; x1++) {
                            count *= dataType.dimensions[x1];
                        }
                        let matrix = [];
                        for (let x2 = 0; x2 < count; x2++) {
                            let record = {};
                            for (let x3 = 0; x3 < dataType.components.length; x3++) {
                                record[dataType.components[x3].name] = await parseComponentData(dataType.components[x3].type, elements.components, elements.replacedStrings);
                            }
                            matrix.push(record);
                        }
                        for (let x4 = dataType.dimensions.length; x4 >= 1; x4--) {
                            matrix = groupObjects(matrix, dataType.dimensions[x4 - 1]);
                        }
                        return Promise.resolve(matrix[0]);
                    } catch (err) {
                        return Promise.reject(`parseRecordMatrix failed >>> ${err}`);
                    }
                }
                async function parseRecord(dataType, valueString) {
                    try {
                        if (dataType.isAlias) {
                            if (symbolTypeCache.hasOwnProperty(dataType.aliasTypeUrl)) {
                                let type = symbolTypeCache[dataType.aliasTypeUrl];
                                return parseRecord(type, valueString);
                            }
                            return Promise.reject("Could not parse record data. Illegal alias value.");
                        }
                        let elements = await getElements(valueString);
                        let record = {};
                        for (let iii = 0; iii < dataType.components.length; iii++) {
                            record[dataType.components[iii].name] = await parseComponentData(dataType.components[iii].type, elements.components, elements.replacedStrings);
                        }
                        return Promise.resolve(record);
                    } catch (err) {
                        return Promise.reject(`parseRecord failed >>> ${err}`);
                    }
                }
                async function parseComponentData(dataType, components, replacedStrings) {
                    try {
                        if (dataType.isAlias) {
                            if (symbolTypeCache.hasOwnProperty(dataType.aliasTypeUrl)) {
                                let type = symbolTypeCache[dataType.aliasTypeUrl];
                                return parseComponentData(type, components, replacedStrings);
                            }
                            return Promise.reject("Could not parse data. Illegal alias value.");
                        }
                        if (dataType.isRecord) {
                            let record = {};
                            for (let iii = 0; iii < dataType.components.length; iii++) {
                                record[dataType.components[iii].name] = await parseComponentData(dataType.components[iii].type, components, replacedStrings);
                            }
                            return Promise.resolve(record);
                        }
                        if (dataType.isAtomic) {
                            let component = components.shift();
                            switch (dataType.type) {
                              case "num":
                              case "dnum":
                                return Promise.resolve(parseFloat(component));

                              case "string":
                                return Promise.resolve(RWS.RapidData.String.cleanupString(replacedStrings[component]));

                              case "bool":
                                let b = component.toUpperCase() == "TRUE";
                                return Promise.resolve(b);

                              default:
                                return Promise.reject("Could not parse data. Illegal atomic value.");
                            }
                        }
                        return Promise.reject("Unknown data type.");
                    } catch (err) {
                        return Promise.reject(`parseComponentData failed >>> ${err}`);
                    }
                }
                this.setValue = function(rapidData, value) {
                    if (typeof rapidData.getDataType === "undefined") {
                        let err = "rapidData is not a valid Data object";
                        RWS.writeDebug(err, 3);
                        return Promise.reject(err);
                    }
                    return rapidData.setValue(value);
                };
            }();
            this.String = new function() {
                this.cleanupString = function(rapidString) {
                    let jsString = "";
                    try {
                        jsString = rapidString.replace(/^"/g, "").replace(/"$/g, "");
                        jsString = jsString.replace(/\\\\/g, "\\");
                        jsString = jsString.replace(/""/g, '"');
                    } catch (err) {
                        jsString = "";
                    }
                    return jsString;
                };
                this.stringify = function(value, s = "") {
                    try {
                        if (typeof value !== "object") {
                            let temp = value.toString();
                            if (typeof value === "string") {
                                temp = temp.replace(/\\/g, "\\\\");
                                temp = temp.replace(/\"/g, '""');
                                temp = `"${temp}"`;
                            }
                            s += temp;
                        } else {
                            s += "[";
                            for (let item in value) {
                                s = this.stringify(value[item], s) + ",";
                            }
                            s = s.slice(0, -1);
                            s += "]";
                        }
                        return s;
                    } catch (error) {
                        RWS.writeDebug(`stringify failed to make a string of '${value.toString()}' >>> ${error}`);
                    }
                };
            }();
        }();
        rd.constructedRapidData = true;
    })(RWS);
}