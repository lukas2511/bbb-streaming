// ==UserScript==
// @name         BBB Stream Controls
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  try to take over the stream!
// @author       Lukas Schauer
// @match        https://*/html5client/*
// @grant        none
// ==/UserScript==

window.streamcontrol = new Object();

(function() {
    'use strict';

    console.log("Activating stream control user script");

    function uiaddon() {
        if(document.getElementById('stream-control-buttons') != undefined) return;
        var msginput = document.getElementById('message-input');
        if (msginput == undefined) {
            return;
        }
        var chat = msginput.parentElement.parentElement.parentElement;
        var buttons = document.createElement('div');
        buttons.id = 'stream-control-buttons';
        buttons.innerHTML = '<button style="margin-right:5px;" onclick="streamcontrol.send_command(\'!view sbs\')">SBS</button>';
        buttons.innerHTML += '<button style="margin-right:5px;" onclick="streamcontrol.send_command(\'!view pip\')">PIP</button>';
        buttons.innerHTML += '<button style="margin-right:5px;" onclick="streamcontrol.send_command(\'!view cam\')">CAM</button>';
        buttons.innerHTML += '<button style="margin-right:5px;" onclick="streamcontrol.send_command(\'!view pres\')">PRES</button>';
        chat.appendChild(buttons);
    }

    function dec2hex (dec) {
        return dec.toString(16).padStart(2, "0")
    }

    // generateId :: Integer -> String
    function generateId (len) {
        var arr = new Uint8Array((len || 40) / 2)
        window.crypto.getRandomValues(arr)
        return Array.from(arr, dec2hex).join('')
    }

    function streamcontroller() {
        if (window.sessionStorage.BBB_authToken == undefined) {
            setTimeout(streamcontroller, 100);
            return;
        }
        var socket = new WebSocket(window.location.href.split("/join")[0].replace("https", "wss") + "/sockjs/494/" + generateId(8) + "/websocket")
        var users = {};
        var chats = {};
        var STREAM_USER = 'stream';

        function send(msg) {
            socket.send(JSON.stringify([JSON.stringify(msg)]))
        }

        function send_command(command) {
            for (var id in users) {
                if(users[id].name == STREAM_USER) {
                    console.log("Sending to " + users[id].userId);
                    chatmsg(chats[users[id].userId], command);
                }
            }
        }
        window.streamcontrol.send_command = send_command;

        function chatmsg(target, msg) {
            send({'msg': 'method', 'method': 'sendGroupChatMsg', 'params': [target, {'color': '0', 'correlationId': window.sessionStorage.BBB_userID + '-' + String(Date.now()), 'sender': {'id': window.sessionStorage.BBB_userID, 'name': window.sessionStorage.BBB_fullname}, 'message': msg}], 'id': String(Date.now())});
        }

        function onmessage(e) {
            if (e.data == 'o') return;
            var msg = JSON.parse(JSON.parse(e.data.substr(1))[0]);
            if (msg.msg == 'ping') {
                send({'msg': 'pong'})
            }

            //if (msg.msg == 'updated' && msg.methods[0] == "2") {
            //    chatmsg('MAIN-PUBLIC-GROUP-CHAT', 'Hello, World! :)');
            //}

            if (msg.collection == 'group-chat') {
                for (var i in msg.fields.users) {
                    if (msg.fields.users[i] == window.sessionStorage.BBB_userID) continue;
                    chats[msg.fields.users[i]] = msg.fields.chatId;
                }
            }

            if (msg.collection == 'users') {
                if(msg.msg == 'added') {
                    users[msg.id] = msg.fields;
                    users[msg.id]._id = msg.id
                } else if(msg.msg == 'changed') {
                    for (var key in msg.fields) {
                        users[msg.id][key] = msg.fields[key]
                    }
                } else {
                    return;
                }
                if(users[msg.id].name == STREAM_USER) {
                    if(chats[users[msg.id].userId] == undefined) {
                        send({'msg': 'method', 'method': 'createGroupChat', 'params': [users[msg.id]], 'id': 'chat-' + users[msg.id].userId})
                    }
                }
            }
        }

        function onopen() {
            console.debug("Websocket connection established.");
            send({'msg': 'connect', 'version': '1', 'support': ['1', 'pre1', 'pre2']});
            send({'msg': 'method', 'method': 'userChangedLocalSettings', 'params': [{'application': {'animations': true, 'chatAudioAlerts': false, 'chatPushAlerts': false, 'fallbackLocale': 'en', 'overrideLocale': null, 'userJoinAudioAlerts': false, 'userJoinPushAlerts': false, 'locale': 'en-US'}, 'audio': {'inputDeviceId': 'undefined', 'outputDeviceId': 'undefined'}, 'dataSaving': {'viewParticipantsWebcams': true, 'viewScreenshare': true}}], 'id': '1'});
            send({'msg': 'method', 'method': 'validateAuthToken', 'params': [window.sessionStorage.BBB_meetingID, window.sessionStorage.BBB_userID, window.sessionStorage.BBB_authToken, window.sessionStorage.BBB_externUserID], 'id': '2'})
            send({'msg': 'sub', 'id': 'sub-group-chat', 'name': 'group-chat', 'params': []});
            send({'msg': 'sub', 'id': 'sub-group-chat-msg', 'name': 'group-chat-msg', 'params': []});
            send({'msg': 'sub', 'id': 'sub-users', 'name': 'users', 'params': []});
        }
        socket.onopen = onopen;
        socket.onmessage = onmessage;
    }

    setTimeout(streamcontroller, 100);
    setInterval(uiaddon, 100);
})();