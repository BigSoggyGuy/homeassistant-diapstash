# Codex-Übergabe — DiapStash Home Assistant Integration

**Übergabestand:** Entwicklungsbasis `v1.1.5`. Die lokale Arbeitskopie verwendet den Branch `dev` auf Basis von `origin/main`-Commit `3bc4b07` (`Release v1.1.5`). Beim Einrichten am 13. November 2026 existierte remote noch kein `dev`-Branch. Die tatsächliche GitHub-Release-/Tag-Lage muss separat geprüft werden; eine Versionsnummer oder Commit-Nachricht beweist keine öffentliche Veröffentlichung.

## Ziel des Projekts

Open-Source-Integration der DiapStash Cloud-Sync API in Home Assistant als HACS Custom Integration. Nutzt ausschließlich die offizielle API und liefert Entitäten für aktuelle Windel, Tragedauer, Booster, Tags, Notizen, Lagerbestand, Wechselstatistik und Waschstatus. **Separate Dashboard-Karten gehören nicht in dieses Repository** (eigenes Projekt `homeassistant-diapstash-card`).

GitHub: `https://github.com/BigSoggyGuy/homeassistant-diapstash`. Domain: `diapstash`. Home-Assistant-Minimum im gelieferten `hacs.json`: `2026.6.0`.

## Architektur / wichtigste Dateien

- `custom_components/diapstash/__init__.py`: Setup/Unload, OAuth2 Session, Migration alter Account-/Gerätezuordnung, Coordinator, Options-Listener. Kritischer Fix: keine Reloads bei Token-only Updates.
- `config_flow.py`: Credentials-Eingabe (Name, Client ID, Client Secret), OAuth2 PKCE, Reauth, Multi-Account-Deduplikation, Options Flow.
- `application_credentials.py`: DiapStash OAuth2 Implementation inkl. Tokenhandling.
- `token.py`: JWT-Payload-`sub` auslesen, ohne Signaturvalidierung (nur für Kontozuordnung, **nicht** als Sicherheitsprüfung).
- `api.py`: API HTTP GET, Token-401-Retry, Pagination, Type-/Brand-Metadaten, History, Booster/Tags/Notiz-Auswertung, Lagerbestände und Statistik. Dataclass `DiapStashCurrentDiaper`.
- `coordinator.py`: Polling über `DataUpdateCoordinator`, optional Stats/Stock.
- `entity.py`: Basisklasse / Availability-Last-Known-Good-Verhalten und DeviceInfo.
- `sensor.py`: Hauptsensor, Dauer-/Lager-/Statistiksensoren und dynamische Detailentitäten.
- `binary_sensor.py`: Tragezustand und Low-Stock-Entitäten.
- `diagnostics.py`: Diagnosedaten; sensiblen Kontext redigieren.
- `const.py`: Domain, API-/OAuth-URLs, Scopes, Polling- und Options-Defaults, Versions-User-Agent.
- `strings.json`, `translations/*.json`: Englisch/Deutsch/Französisch/Spanisch.
- `custom_components/diapstash/brand/` und `brand/`: Icons/Logos für Integration und HACS/HA.
- `.github/workflows/hacs.yaml`, `hassfest.yaml`: bestehende CI.

## Bewährte Kernfunktionen

### Aktuelle Windel, Booster, Tags/Notizen

- History-Endpunkt: `/history/changes` (Cloud Sync, sort `startTime,desc`). Die primäre Windel bleibt Hauptwert des `current_diaper`-Sensors.
- `current_items`: alle aktuellen Change-Items mit Rolle und Typinformationen.
- `boosters`, `boosters_count`, `boosters_label`: zusätzliche Einlagen/Booster; bestätigter Funktionstest im früheren Dev-Stand.
- API-Felder `tags` und `note` wurden mit Nutzertest **bestätigt**. Sichtbare HA-Attribute `change_tags` als **Liste**, `change_tags_label` als Text, `change_note` als optionaler Text, `change_has_note` als bool.
- Keine dauerhaften ungeschützten Rohdaten oder kompletten History-JSONs als Sensorattribute hinzufügen.
- Zeitdauer wird lokal in HA aktualisiert (Default 5 Minuten), ohne jedes Mal den Cloud-Endpunkt aufzurufen.

### Verfügbarkeit und OAuth-Stabilität

- Anfangs gab es kurzzeitige HA-History-Sprünge `Wert → Nicht verfügbar → Wert`.
- Die Ursache war nach Test sehr wahrscheinlich **Token-refresh → ConfigEntry update listener → unnötiger Komplett-Reload**. In `__init__.py` werden Optionen mit `coordinator.last_options` verglichen, Reload nur bei tatsächlichen Optionsänderungen; der Nutzer bestätigte danach keine neuen „Nicht verfügbar“-Einträge.
- `entity.py` hält zuvor erfolgreich geladene Coordinator-Daten bei vorübergehenden API-Problemen verfügbar. Auth-/Reauth-Fehler nicht verstecken.
- Die Version `v1.0.2` brachte `async_step_reauth` / `async_step_reauth_confirm`; Reauth aktualisiert dasselbe Konto und darf keine zusätzliche Instanz anlegen.

### Multi-Account und Stock

- Jeder DiapStash-Account benutzt eigene API-Client-ID/Secret.
- `sub`-Claim dient als stabile Konto-ID, Duplicate-Checks für Konto und Client ID sind relevant.
- Lager: Stocks, Disposables, Reusables und Details nach Marken, Typ/Größe und Lagerorten. Reusables werden getrennt von Einweg-Bestand im Wash-Status behandelt. Achte auf boolesche Strings wie `"false"`.
- Dynamische per-Brand/per-Type und Low-Stock-Entitäten; Entity Unique IDs dürfen ohne Migration nicht geändert werden.
- Einstellbar: Polling 15/30/60 Min; lokale Dauer 0/1/5/15 Min; Stock/Stats/Dynamik/Low Stock, Schwelle (Standard 10).

## API und Auth

- API base: `https://api.diapstash.com/api/v1` (Fallback `https://api.diapstash.com/api` in der vorhandenen Implementierung).
- OAuth: `https://account.diapstash.com/oidc/auth`, `https://account.diapstash.com/oidc/token`.
- API Header: Bearer-Token, `DS-API-CLIENT-ID`, spezifischer `User-Agent`.
- Scopes: `cloud-sync.history`, `cloud-sync.stock`, `cloud-sync.types`, `offline_access`.
- Datenabruf im Code: Pagination ab `page=0`, Seitengröße `50`, page++ bis Ende/totalCount.
- Nutze ausschließlich die öffentliche API; keine Katalogseiten scrapen. Öffentliche API ist aktuell lesend; keine Schreiboperationen voraussetzen.
- README und Setup-Dialog enthalten DiapStash-Link zum Vorbefüllen der API-Client-Erstellung, inklusive Scopes und Redirect-URL `https://my.home-assistant.io/redirect/oauth`.

## Bekannter offener Punkt / keine falschen Erfolgsmeldungen

**HACS-/HA-Update-Kachel zeigte das DiapStash-Logo weiterhin nicht**, obwohl sowohl Root-Brand-Assets (`brand/`) als auch Integrations-Assets (`custom_components/diapstash/brand/`) vorhanden waren. Dies wurde nach v1.1.4 erneut beobachtet. Ursache noch nicht abschließend geklärt. Gegebenenfalls HACS, HA Brands API, Asset-Anforderungen und tatsächlich ausgelieferte Inhalte kontrollieren; **nicht** automatisch als behoben markieren.

## Freigabe- und Arbeitsregeln

- Nach Wunsch des Besitzers neue Features/Fixes **ausschließlich im `dev` oder `dev/*`-Branch**, nicht direkt auf `main`.
- Version 1.1.5 ist die aktuelle Entwicklungsbasis. Release-/Tag-Status separat gegen GitHub überprüfen.
- Keine heimlichen Versionssprünge, Releases, Merges oder Pushes.
- Zuerst vorhandenen Zustand testen, dann Änderungen mit kleinem Diff und Regressionstests.
- Keine echten Secrets / Tokens in Dateien oder Logs speichern oder ausgeben.

## Übergabe / Arbeitsbeginn für Codex

1. `AGENTS.md` vollständig lesen.
2. `docs/ARCHITECTURE.md`, `README.md`, `CHANGELOG.md` lesen und bei Bedarf Code prüfen.
3. `git status`, aktuellen Branch und Remote-Basis prüfen, wenn Git-Metadaten vorhanden sind.
4. `python tools/check_project.py` sowie `python -m unittest discover -s tests -v` ausführen.
5. Kurze Architektur-/Risikozusammenfassung erstellen; **ohne expliziten Auftrag noch keinen Produktivcode verändern**.
