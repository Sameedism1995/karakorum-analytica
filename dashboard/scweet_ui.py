"""Full X / Scweet explorer tab for the Karakorum Analytica dashboard."""

from __future__ import annotations

from datetime import date, timedelta
from types import ModuleType
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.ui_components import render_raw_news_cards

SOURCE_NAME = "X/Scweet"
TWEET_TYPE_OPTIONS = [
    "all",
    "originals_only",
    "replies_only",
    "retweets_only",
    "exclude_replies",
    "exclude_retweets",
]
DISPLAY_TYPES = ["Top", "Latest"]
SAVE_FORMATS = ["", "csv", "json", "both"]


def _status_pill(ok: bool, label_ok: str, label_bad: str) -> str:
    css = "status-connected" if ok else "status-disconnected"
    label = label_ok if ok else label_bad
    return f'<span class="status-pill {css}">{label}</span>'


def _default_since(days: int = 7) -> str:
    return (date.today() - timedelta(days=days)).isoformat()


def _render_status_cards(scweet: dict[str, Any]) -> None:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("**Enabled**")
        st.markdown(_status_pill(scweet.get("enabled"), "Yes", "No"), unsafe_allow_html=True)
    with c2:
        st.markdown("**Configured**")
        st.markdown(_status_pill(scweet.get("configured"), "Yes", "No"), unsafe_allow_html=True)
    with c3:
        cached = bool(scweet.get("session_cached") or scweet.get("has_auth_token"))
        st.markdown("**Session**")
        st.markdown(_status_pill(cached, "Cached", "Not cached"), unsafe_allow_html=True)
    with c4:
        st.markdown("**Client**")
        st.markdown(_status_pill(scweet.get("client_ok"), "Ready", "Not ready"), unsafe_allow_html=True)


def _output_options(prefix: str) -> dict[str, Any]:
    c1, c2, c3 = st.columns(3)
    with c1:
        save = st.checkbox("Save to disk", key=f"{prefix}_save")
    with c2:
        save_format = st.selectbox("Save format", SAVE_FORMATS, key=f"{prefix}_save_format")
    with c3:
        save_name = st.text_input("Save name (optional)", key=f"{prefix}_save_name")
    return {
        "save": save,
        "save_format": save_format or None,
        "save_name": save_name.strip() or None,
    }


def _pagination_options(prefix: str, *, default_limit: int) -> dict[str, Any]:
    c1, c2, c3 = st.columns(3)
    with c1:
        limit = st.number_input("Limit", min_value=1, max_value=5000, value=default_limit, key=f"{prefix}_limit")
    with c2:
        resume = st.checkbox("Resume checkpoint", key=f"{prefix}_resume")
    with c3:
        max_empty = st.number_input(
            "Max empty pages",
            min_value=0,
            max_value=20,
            value=0,
            help="0 = Scweet default",
            key=f"{prefix}_max_empty",
        )
    opts: dict[str, Any] = {"limit": int(limit), "resume": resume}
    if max_empty > 0:
        opts["max_empty_pages"] = int(max_empty)
    return opts


def _run_operation(
    backend: ModuleType,
    base_url: str,
    operation: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    with st.spinner(f"Running Scweet {operation.replace('_', ' ')}…"):
        return backend.run_scweet_operation(base_url, operation=operation, params=params)


def _render_tweet_results(result: dict[str, Any]) -> None:
    items = result.get("items") or []
    raw = result.get("raw") or []
    st.success(f"Returned {result.get('count', len(items))} tweet(s).")

    if raw:
        rows = []
        for tweet in raw:
            user = tweet.get("user") or {}
            rows.append(
                {
                    "user": user.get("screen_name") or user.get("username"),
                    "text": (tweet.get("text") or "")[:180],
                    "likes": tweet.get("likes"),
                    "retweets": tweet.get("retweets"),
                    "replies": tweet.get("comments"),
                    "url": tweet.get("tweet_url"),
                    "timestamp": tweet.get("timestamp"),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if items:
        preview_df = pd.DataFrame(
            [
                {
                    "source_name": item.get("source_name") or SOURCE_NAME,
                    "title": item.get("title"),
                    "summary": item.get("summary"),
                    "url": item.get("url"),
                    "published_at": item.get("published_at"),
                    "collected_at": None,
                    "city": item.get("city"),
                    "province": item.get("province"),
                    "keywords": None,
                    "status": "preview",
                }
                for item in items
            ]
        )
        render_raw_news_cards(preview_df.head(25))

    with st.expander("Raw JSON"):
        st.json(raw[:10] if len(raw) > 10 else raw)


def _render_user_results(result: dict[str, Any]) -> None:
    items = result.get("items") or []
    st.success(f"Returned {result.get('count', len(items))} profile(s).")
    if not items:
        return

    rows = []
    for user in items:
        rows.append(
            {
                "username": user.get("username"),
                "name": user.get("name"),
                "followers": user.get("followers_count"),
                "following": user.get("following_count"),
                "verified": user.get("verified"),
                "blue_verified": user.get("blue_verified"),
                "location": user.get("location"),
                "description": (user.get("description") or "")[:120],
                "type": user.get("type") or user.get("input"),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("Raw JSON"):
        st.json(items[:10] if len(items) > 10 else items)


def _render_session_tab(
    backend: ModuleType,
    base_url: str,
    scweet: dict[str, Any],
) -> None:
    st.markdown("**Connection**")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("Connect / refresh session", type="primary", use_container_width=True):
            with st.spinner("Logging into X (complete verification if prompted)…"):
                result = backend.refresh_scweet_session(base_url, force=True)
            if result.get("ok"):
                st.success(result.get("message") or "Session refreshed.")
                st.rerun()
            else:
                st.error(result.get("error") or "Session refresh failed.")

    with c2:
        st.markdown(
            f"- Auto-login: **{'on' if scweet.get('auto_login') else 'off'}**\n"
            f"- Headless login: **`SCWEET_LOGIN_HEADLESS`** in `.env`\n"
            f"- DB: `{scweet.get('db_path', '—')}`\n"
            f"- Default pipeline query: see Search tab"
        )

    st.divider()
    st.markdown("**Account pool (ScweetDB)**")
    pool = backend.get_scweet_accounts(base_url)
    if not pool.get("ok"):
        st.warning(pool.get("error") or "Could not load account pool.")
        return

    summary = pool.get("summary") or {}
    if summary.get("total", 0):
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Accounts", summary.get("total", 0))
        m2.metric("Eligible", summary.get("eligible", 0))
        m3.metric("With token", summary.get("with_auth_token", 0))
        m4.metric("Cooling down", summary.get("cooling_down", 0))
    else:
        st.info("No accounts in Scweet DB yet — connect session to provision your X account.")

    accounts = pool.get("accounts") or []
    if accounts:
        st.dataframe(pd.DataFrame(accounts), use_container_width=True, hide_index=True)

    runs = pool.get("runs") or []
    if runs:
        st.markdown("**Recent runs**")
        st.dataframe(pd.DataFrame(runs), use_container_width=True, hide_index=True)


def _render_search_tab(backend: ModuleType, base_url: str, scweet: dict[str, Any]) -> None:
    default_query = scweet.get("default_query") or "Pakistan security lang:en"
    st.caption("Advanced X search with Scweet filters. Always set a limit to protect account quota.")

    with st.form("scweet_search_form"):
        query = st.text_area("Query string", value=default_query, height=80)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            since = st.date_input("Since", value=date.fromisoformat(_default_since(7)))
        with c2:
            until = st.date_input("Until", value=date.today())
        with c3:
            lang = st.text_input("Language", value="en")
        with c4:
            display_type = st.selectbox("Display", DISPLAY_TYPES)

        st.markdown("**Structured filters** (comma-separated lists)")
        f1, f2, f3 = st.columns(3)
        with f1:
            all_words = st.text_input("All words (AND)")
            any_words = st.text_input("Any words (OR)")
            exact_phrases = st.text_input("Exact phrases")
        with f2:
            exclude_words = st.text_input("Exclude words")
            hashtags_any = st.text_input("Hashtags (any)")
            hashtags_exclude = st.text_input("Hashtags (exclude)")
        with f3:
            from_users = st.text_input("From users")
            to_users = st.text_input("To users")
            mentioning_users = st.text_input("Mentioning users")

        g1, g2, g3 = st.columns(3)
        with g1:
            tweet_type = st.selectbox("Tweet type", TWEET_TYPE_OPTIONS)
            min_likes = st.number_input("Min likes", min_value=0, value=0)
            min_replies = st.number_input("Min replies", min_value=0, value=0)
        with g2:
            min_retweets = st.number_input("Min retweets", min_value=0, value=0)
            place = st.text_input("Place")
            near = st.text_input("Near")
        with g3:
            within = st.text_input("Within radius", placeholder="15mi")
            geocode = st.text_input("Geocode", placeholder="lat,lon,radius")

        st.markdown("**Content filters**")
        b1, b2, b3, b4, b5, b6, b7 = st.columns(7)
        verified_only = b1.checkbox("Verified only")
        blue_verified_only = b2.checkbox("Blue verified")
        has_images = b3.checkbox("Has images")
        has_videos = b4.checkbox("Has videos")
        has_links = b5.checkbox("Has links")
        has_mentions = b6.checkbox("Has mentions")
        has_hashtags = b7.checkbox("Has hashtags")

        pagination = _pagination_options("search", default_limit=50)
        output = _output_options("search")
        submitted = st.form_submit_button("Run search", type="primary")

    if submitted:
        params: dict[str, Any] = {
            "query": query,
            "since": since.isoformat(),
            "until": until.isoformat(),
            "lang": lang.strip() or None,
            "display_type": display_type,
            "tweet_type": tweet_type,
            "all_words": all_words,
            "any_words": any_words,
            "exact_phrases": exact_phrases,
            "exclude_words": exclude_words,
            "hashtags_any": hashtags_any,
            "hashtags_exclude": hashtags_exclude,
            "from_users": from_users,
            "to_users": to_users,
            "mentioning_users": mentioning_users,
            "place": place.strip() or None,
            "near": near.strip() or None,
            "within": within.strip() or None,
            "geocode": geocode.strip() or None,
            "verified_only": verified_only,
            "blue_verified_only": blue_verified_only,
            "has_images": has_images,
            "has_videos": has_videos,
            "has_links": has_links,
            "has_mentions": has_mentions,
            "has_hashtags": has_hashtags,
            **pagination,
            **output,
        }
        if min_likes > 0:
            params["min_likes"] = int(min_likes)
        if min_replies > 0:
            params["min_replies"] = int(min_replies)
        if min_retweets > 0:
            params["min_retweets"] = int(min_retweets)

        result = _run_operation(backend, base_url, "search", params)
        if result.get("ok"):
            _render_tweet_results(result)
        else:
            st.error(result.get("error") or "Search failed.")


def _render_profile_tab(backend: ModuleType, base_url: str) -> None:
    with st.form("scweet_profile_form"):
        users = st.text_input("Usernames or profile URLs", placeholder="kkanalytica, x.com/someuser")
        pagination = _pagination_options("profile", default_limit=50)
        output = _output_options("profile")
        submitted = st.form_submit_button("Fetch profile tweets", type="primary")

    if submitted:
        params = {"users": users, **pagination, **output}
        result = _run_operation(backend, base_url, "profile_tweets", params)
        if result.get("ok"):
            _render_tweet_results(result)
        else:
            st.error(result.get("error") or "Profile tweets failed.")


def _render_follows_tab(backend: ModuleType, base_url: str) -> None:
    tab_followers, tab_following = st.tabs(["Followers", "Following"])

    with tab_followers:
        with st.form("scweet_followers_form"):
            users = st.text_input("Target users", placeholder="elonmusk", key="followers_users")
            raw_json = st.checkbox("Include raw GraphQL payload", key="followers_raw")
            pagination = _pagination_options("followers", default_limit=100)
            output = _output_options("followers")
            submitted = st.form_submit_button("Fetch followers", type="primary")

        if submitted:
            params = {"users": users, "raw_json": raw_json, **pagination, **output}
            result = _run_operation(backend, base_url, "followers", params)
            if result.get("ok"):
                _render_user_results(result)
            else:
                st.error(result.get("error") or "Followers fetch failed.")

    with tab_following:
        with st.form("scweet_following_form"):
            users = st.text_input("Target users", placeholder="OpenAI", key="following_users")
            raw_json = st.checkbox("Include raw GraphQL payload", key="following_raw")
            pagination = _pagination_options("following", default_limit=100)
            output = _output_options("following")
            submitted = st.form_submit_button("Fetch following", type="primary")

        if submitted:
            params = {"users": users, "raw_json": raw_json, **pagination, **output}
            result = _run_operation(backend, base_url, "following", params)
            if result.get("ok"):
                _render_user_results(result)
            else:
                st.error(result.get("error") or "Following fetch failed.")


def _render_user_info_tab(backend: ModuleType, base_url: str) -> None:
    with st.form("scweet_user_info_form"):
        users = st.text_input("Usernames or profile URLs", placeholder="kkanalytica, Reuters")
        output = _output_options("user_info")
        submitted = st.form_submit_button("Fetch user info", type="primary")

    if submitted:
        params = {"users": users, **output}
        result = _run_operation(backend, base_url, "user_info", params)
        if result.get("ok"):
            _render_user_results(result)
        else:
            st.error(result.get("error") or "User info failed.")


def _render_collected_tab(raw_df: pd.DataFrame) -> None:
    scweet_df = pd.DataFrame()
    if not raw_df.empty and "source_name" in raw_df.columns:
        scweet_df = raw_df[raw_df["source_name"] == SOURCE_NAME].copy()

    if scweet_df.empty:
        st.info(
            "No X/Scweet items stored yet. Use Search above or **Run Collection Now** "
            "from the sidebar to ingest tweets into the pipeline."
        )
        return

    st.caption(f"{len(scweet_df)} tweet(s) from collection runs")
    render_raw_news_cards(scweet_df.head(100))


def render_scweet_tab(
    backend: ModuleType,
    base_url: str,
    *,
    health_ok: bool,
    raw_df: pd.DataFrame,
) -> None:
    """Render the full X / Scweet explorer tab."""
    st.markdown('<div class="section-title">X / Scweet explorer</div>', unsafe_allow_html=True)
    st.caption(
        "Full Scweet toolkit: search, profile timelines, followers/following, "
        "user profiles, session management, and pipeline-collected tweets."
    )

    if not health_ok:
        st.warning("Backend unavailable — Scweet controls cannot run.")
        return

    status_result = backend.get_scweet_status(base_url)
    scweet = (status_result.get("data") or {}).get("scweet") or {}
    if not status_result.get("ok"):
        st.error(status_result.get("error") or "Could not load Scweet status.")
        return

    _render_status_cards(scweet)

    if scweet.get("error"):
        st.markdown(
            f'<div class="error-box"><strong>Scweet error:</strong> {scweet["error"]}</div>',
            unsafe_allow_html=True,
        )
    if scweet.get("enabled") and not scweet.get("configured"):
        st.markdown(
            '<div class="warn-box"><strong>Scweet enabled but not configured.</strong> '
            "Set <code>SCWEET_USERNAME</code> and <code>SCWEET_PASSWORD</code> in `.env`.</div>",
            unsafe_allow_html=True,
        )

    st.divider()

    tab_session, tab_search, tab_profile, tab_follows, tab_users, tab_collected = st.tabs(
        ["Session", "Search", "Profile tweets", "Followers / Following", "User info", "Collected"]
    )

    with tab_session:
        _render_session_tab(backend, base_url, scweet)
    with tab_search:
        _render_search_tab(backend, base_url, scweet)
    with tab_profile:
        _render_profile_tab(backend, base_url)
    with tab_follows:
        _render_follows_tab(backend, base_url)
    with tab_users:
        _render_user_info_tab(backend, base_url)
    with tab_collected:
        _render_collected_tab(raw_df)
