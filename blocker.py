"""Built-in tracker blocking as a WebKit content-blocker rule list.

shortcut: a hand-picked list of major ad/analytics domains, not EasyList; load a converted list if you need uBlock-level coverage.
"""
import json

TRACKERS = (
    # analytics and tag managers
    "google-analytics.com", "googletagmanager.com", "googletagservices.com", "analytics.google.com",
    "hotjar.com", "mixpanel.com", "segment.io", "cdn.segment.com", "amplitude.com", "fullstory.com", "mouseflow.com",
    "clarity.ms", "chartbeat.com", "chartbeat.net", "nr-data.net", "quantserve.com", "quantcount.com",
    "scorecardresearch.com", "mc.yandex.ru", "js.hs-analytics.net", "track.hubspot.com", "heapanalytics.com",
    "kissmetrics.com", "crazyegg.com", "omtrdc.net", "demdex.net", "everesttech.net", "krxd.net", "bluekai.com",
    # ad networks
    "doubleclick.net", "googlesyndication.com", "googleadservices.com", "adservice.google.com",
    "amazon-adsystem.com", "adnxs.com", "criteo.com", "criteo.net", "taboola.com", "outbrain.com",
    "pubmatic.com", "rubiconproject.com", "openx.net", "casalemedia.com", "moatads.com", "adsrvr.org",
    "teads.tv", "smartadserver.com", "media.net", "adform.net", "bidswitch.net", "sharethrough.com", "3lift.com",
    "indexww.com", "yieldmo.com", "zedo.com", "advertising.com", "adroll.com", "lijit.com", "gumgum.com",
    # social tracking pixels
    "connect.facebook.net", "pixel.facebook.com", "ads-twitter.com", "analytics.twitter.com",
    "px.ads.linkedin.com", "snap.licdn.com", "analytics.tiktok.com", "tr.snapchat.com", "sc-static.net",
    "bat.bing.com", "ct.pinterest.com", "alb.reddit.com",
)


def rules_json(exceptions=()):
    """Block rules, then one rule that lifts them on pages from the user's exception hosts (and their subdomains)."""
    # WebKit's rule regexes have no alternation, so each domain gets its own rule; third-party loads only.
    rules = [
        {"trigger": {"url-filter": "^[^:]+://+([^:/]+\\.)?" + d.replace(".", "\\.") + "[:/]",
                     "load-type": ["third-party"]},
         "action": {"type": "block"}}
        for d in TRACKERS
    ]
    if exceptions:
        rules.append({"trigger": {"url-filter": ".*", "if-domain": ["*" + h for h in exceptions]},
                      "action": {"type": "ignore-previous-rules"}})
    return json.dumps(rules)
