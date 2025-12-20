/*
 Copyright (c) 2024 glaumar <glaumar@geekgo.tech>

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program. If not, see <https://www.gnu.org/licenses/>.
 */

#include "vrp_torrent.h"
#include "app_settings.h"

#include <QCoroNetworkReply>
#include <QCoroSignal>
#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>

VrpTorrent::VrpTorrent(QObject *parent)
    : QObject(parent)
{
    loadTorrents();
}

VrpTorrent::~VrpTorrent()
{
    saveTorrents();
}

QCoro::Task<bool> VrpTorrent::update()
{
    static const QString url = "https://torrents.vrpirates.wiki/torrents.json";

    QNetworkRequest request(url);
    auto *reply = manager_.get(request);
    co_await qCoro(reply, &QNetworkReply::finished);

    if (reply->error() != QNetworkReply::NoError) {
        qDebug() << "Downloading torrents.json Error: " << reply->errorString();
        co_return false;
    }

    auto data = reply->readAll();
    QJsonDocument doc = QJsonDocument::fromJson(data);
    if (doc.isNull()) {
        qDebug() << "Parsing torrents.json Error: " << data;
        co_return false;
    }

    QJsonArray jsonArray = doc.array();
    magnet_uri_.clear();
    for (const QJsonValue &value : jsonArray) {
        QJsonObject obj = value.toObject();
        QString release_name = obj["name"].toString();
        QString magnet_uri = obj["magnet_uri"].toString();
        magnet_uri_[release_name] = magnet_uri;
    }
    saveTorrents();
    co_return true;
}

void VrpTorrent::loadTorrents()
{
    QString path = AppSettings::instance()->dataPath() + "/torrents.json";
    QFile file(path);
    if (!file.exists() || !file.open(QIODevice::ReadOnly)) {
        return;
    }

    QByteArray data = file.readAll();
    QJsonDocument doc = QJsonDocument::fromJson(data);
    if (doc.isNull()) {
        return;
    }

    QJsonArray jsonArray = doc.array();
    magnet_uri_.clear();
    for (const QJsonValue &value : jsonArray) {
        QJsonObject obj = value.toObject();
        QString release_name = obj["name"].toString();
        QString magnet_uri = obj["magnet_uri"].toString();
        magnet_uri_[release_name] = magnet_uri;
    }
}

void VrpTorrent::saveTorrents()
{
    if (magnet_uri_.isEmpty()) {
        return;
    }

    QString path = AppSettings::instance()->dataPath() + "/torrents.json";
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly)) {
        return;
    }

    QJsonArray jsonArray;
    for (auto it = magnet_uri_.constBegin(); it != magnet_uri_.constEnd(); ++it) {
        QJsonObject obj;
        obj["name"] = it.key();
        obj["magnet_uri"] = it.value();
        jsonArray.append(obj);
    }

    QJsonDocument doc(jsonArray);
    file.write(doc.toJson());
}
