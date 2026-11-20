


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

fpComponentsLoadCSS("fp-components/fp-components-button-a.css");

var FPComponents = FPComponents || {};

(function(o) {
    if (!o.hasOwnProperty("Button_A")) {
        o.Button_A = class {
            constructor() {
                this._anchor = null;
                this._root = null;
                this._divIcon = null;
                this._divText = null;
                this._icon = null;
                this._enabled = true;
                this._onclick = null;
                this._text = "";
                this._highlight = false;
            }
            get parent() {
                return this._anchor;
            }
            get onclick() {
                return this._onclick;
            }
            set onclick(f) {
                this._onclick = f;
            }
            get enabled() {
                return this._enabled;
            }
            set enabled(e) {
                this._enabled = e ? true : false;
                this._updateClassNames();
            }
            get text() {
                return this._text;
            }
            set text(t) {
                this._text = t;
                if (this._divText !== null) {
                    this._divText.textContent = t;
                }
            }
            get highlight() {
                return this._highlight;
            }
            set highlight(h) {
                this._highlight = h ? true : false;
                this._updateClassNames();
            }
            get icon() {
                return this._icon;
            }
            set icon(i) {
                this._icon = i === null ? null : i.replace(/\\/g, "/");
                if (this._root == null) {
                    return;
                }
                if (!i) {
                    if (this._divIcon !== null) {
                        this._root.removeChild(this._divIcon);
                        this._divIcon = null;
                    }
                    return;
                }
                if (this._divIcon == null) {
                    this._addIcon();
                    return;
                }
                this._divIcon.style.backgroundImage = `url("${this._urlEncode(this._icon)}")`;
            }
            _urlEncode(url) {
                const urlItems = url.split("/");
                const escapedItems = [];
                for (const item of urlItems) {
                    escapedItems.push(encodeURIComponent(item));
                }
                return escapedItems.join("/");
            }
            _updateClassNames() {
                if (this._root !== null) {
                    this._root.className = this._enabled === true ? "fp-components-button" : "fp-components-button-disabled";
                    if (this._highlight) {
                        this._root.className += " fp-components-button-highlight";
                    }
                }
            }
            attachToId(nodeId) {
                let element = document.getElementById(nodeId);
                if (element === null) {
                    console.log("Could not find element with id: " + nodeId);
                    return false;
                }
                return this.attachToElement(element);
            }
            attachToElement(element) {
                this._anchor = element;
                return this.rebuild();
            }
            _addIcon() {
                if (this._root) {
                    this._divIcon = document.createElement("div");
                    this._divIcon.style.backgroundImage = `url("${this._urlEncode(this._icon)}")`;
                    this._divIcon.className = "fp-components-button-icon";
                    this._root.prepend(this._divIcon);
                }
            }
            rebuild() {
                let divButton = document.createElement("div");
                let divText = document.createElement("span");
                divText.className = "fp-components-button-text";
                divText.textContent = this._text;
                divButton.onclick = () => {
                    if (this._onclick !== null && this._enabled === true) {
                        this._onclick();
                    }
                };
                divButton.appendChild(divText);
                this._root = divButton;
                this._divText = divText;
                if (this._icon) {
                    this._addIcon();
                }
                this._updateClassNames();
                this._anchor.appendChild(divButton);
            }
        };
        o.Button_A.VERSION = "1.6.0";
    }
})(FPComponents);