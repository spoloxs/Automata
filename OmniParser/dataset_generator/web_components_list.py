"""
Comprehensive list of ALL webpage UI components for YOLO training dataset generation

Based on research from:
- https://careerfoundry.com/en/blog/ui-design/ui-element-glossary/
- https://developer.mozilla.org/en-US/docs/Web/HTML/Element
- https://medium.com/@oliviarizona/list-of-ui-components-4de586025dad
"""

# Complete categorized list of all webpage components
WEB_COMPONENTS = {
    # NAVIGATION
    "navigation": [
        "navbar",
        "top_bar",
        "header",
        "sticky_header",
        "mega_menu",
        "dropdown_menu",
        "hamburger_menu",
        "sidebar",
        "left_sidebar",
        "right_sidebar",
        "breadcrumbs",
        "tabs",
        "pagination",
        "footer",
        "sticky_footer",
        "floating_action_button",
        "bottom_nav",
        "step_indicator",
        "progress_nav",
    ],

    # BUTTONS & CONTROLS
    "buttons": [
        "primary_button",
        "secondary_button",
        "tertiary_button",
        "icon_button",
        "fab_button",
        "toggle_button",
        "split_button",
        "button_group",
        "radio_button",
        "checkbox",
        "switch_toggle",
        "chip",
        "tag",
        "badge",
        "pill_button",
        "ghost_button",
        "outline_button",
    ],

    # FORMS & INPUT
    "forms": [
        "text_input",
        "password_input",
        "email_input",
        "number_input",
        "tel_input",
        "url_input",
        "search_input",
        "textarea",
        "select_dropdown",
        "multiselect",
        "autocomplete",
        "combobox",
        "date_picker",
        "time_picker",
        "datetime_picker",
        "range_picker",
        "color_picker",
        "file_upload",
        "drag_drop_upload",
        "image_upload",
        "slider",
        "range_slider",
        "rating",
        "star_rating",
        "form_validation",
        "captcha",
        "otp_input",
    ],

    # CONTENT DISPLAY
    "content": [
        "card",
        "media_card",
        "product_card",
        "profile_card",
        "pricing_card",
        "testimonial_card",
        "article_card",
        "list",
        "unordered_list",
        "ordered_list",
        "description_list",
        "table",
        "data_table",
        "comparison_table",
        "pricing_table",
        "grid",
        "masonry_grid",
        "tile_grid",
        "timeline",
        "feed",
        "kanban_board",
    ],

    # MEDIA
    "media": [
        "image",
        "gallery",
        "carousel",
        "slideshow",
        "image_slider",
        "lightbox",
        "video_player",
        "youtube_embed",
        "vimeo_embed",
        "audio_player",
        "podcast_player",
        "waveform",
        "thumbnail",
        "avatar",
        "icon",
        "emoji",
        "logo",
        "background_image",
        "background_video",
        "gif",
        "svg_graphic",
    ],

    # OVERLAYS & MODALS
    "overlays": [
        "modal",
        "dialog",
        "popup",
        "lightbox_modal",
        "fullscreen_modal",
        "drawer",
        "side_panel",
        "bottom_sheet",
        "popover",
        "tooltip",
        "dropdown",
        "context_menu",
        "overlay",
        "backdrop",
        "cookie_consent",
        "terms_popup",
        "privacy_notice",
        "newsletter_popup",
        "exit_intent_popup",
        "age_verification",
    ],

    # NOTIFICATIONS & FEEDBACK
    "notifications": [
        "toast",
        "snackbar",
        "alert",
        "success_alert",
        "error_alert",
        "warning_alert",
        "info_alert",
        "banner",
        "notification_bell",
        "notification_badge",
        "notification_center",
        "push_notification",
        "inline_notification",
        "progress_bar",
        "progress_circle",
        "spinner",
        "skeleton_loader",
        "loading_dots",
        "shimmer_effect",
        "empty_state",
        "error_page",
        "404_page",
    ],

    # SPECIALIZED COMPONENTS
    "specialized": [
        "crossword",
        "puzzle_grid",
        "sudoku_grid",
        "calendar",
        "event_calendar",
        "booking_calendar",
        "chart",
        "bar_chart",
        "line_chart",
        "pie_chart",
        "donut_chart",
        "area_chart",
        "scatter_plot",
        "heatmap",
        "map",
        "google_maps",
        "interactive_map",
        "weather_widget",
        "clock_widget",
        "countdown_timer",
        "qr_code",
        "barcode",
        "chat_widget",
        "chatbot",
        "live_chat",
        "comments_section",
        "social_share_buttons",
        "like_button",
        "bookmark_button",
    ],

    # ADS & MARKETING
    "ads": [
        "banner_ad",
        "leaderboard_ad",
        "skyscraper_ad",
        "rectangle_ad",
        "popup_ad",
        "interstitial_ad",
        "native_ad",
        "sponsored_content",
        "affiliate_banner",
        "promo_banner",
        "discount_banner",
        "flash_sale_banner",
    ],

    # ECOMMERCE
    "ecommerce": [
        "shopping_cart",
        "cart_icon",
        "mini_cart",
        "wishlist",
        "compare_products",
        "product_grid",
        "product_filter",
        "faceted_search",
        "price_range",
        "size_selector",
        "color_selector",
        "quantity_selector",
        "add_to_cart_button",
        "buy_now_button",
        "checkout_form",
        "payment_form",
        "shipping_info",
        "order_summary",
        "coupon_input",
        "gift_card",
        "recently_viewed",
        "related_products",
        "upsell_section",
        "cross_sell",
        "stock_indicator",
        "sale_badge",
        "new_badge",
        "bestseller_badge",
    ],

    # SOCIAL & USER
    "social": [
        "login_form",
        "signup_form",
        "social_login",
        "oauth_buttons",
        "user_profile",
        "profile_header",
        "profile_photo",
        "cover_photo",
        "bio_section",
        "follow_button",
        "share_button",
        "like_counter",
        "view_counter",
        "social_feed",
        "post_card",
        "comment_box",
        "reply_thread",
        "mention",
        "hashtag",
        "emoji_picker",
        "gif_picker",
        "status_indicator",
        "online_status",
        "typing_indicator",
    ],

    # ACCESSIBILITY
    "accessibility": [
        "skip_to_content",
        "accessibility_menu",
        "font_size_control",
        "contrast_toggle",
        "screen_reader_text",
        "keyboard_navigation",
        "focus_indicator",
        "aria_live_region",
        "language_selector",
    ],

    # TEXT & TYPOGRAPHY
    "typography": [
        "heading_h1",
        "heading_h2",
        "heading_h3",
        "heading_h4",
        "heading_h5",
        "heading_h6",
        "paragraph",
        "blockquote",
        "code_block",
        "inline_code",
        "preformatted_text",
        "link",
        "anchor_link",
        "hyperlink",
        "text_highlight",
        "strikethrough",
        "underline",
        "bold_text",
        "italic_text",
        "subscript",
        "superscript",
        "abbreviation",
        "definition",
        "caption",
        "label",
        "placeholder_text",
    ],

    # LAYOUT STRUCTURES
    "layout": [
        "container",
        "section",
        "div_block",
        "flex_container",
        "grid_container",
        "column_layout",
        "hero_section",
        "feature_section",
        "cta_section",
        "testimonial_section",
        "faq_section",
        "pricing_section",
        "team_section",
        "contact_section",
        "parallax_section",
        "full_width_section",
        "boxed_section",
        "split_screen",
        "accordion",
        "collapsible",
        "expansion_panel",
        "divider",
        "spacer",
        "separator",
    ],

    # INTERACTIVE
    "interactive": [
        "drag_and_drop",
        "sortable_list",
        "reorderable_items",
        "resizable_panel",
        "splitter",
        "zoom_control",
        "pan_control",
        "scroll_to_top",
        "infinite_scroll",
        "lazy_load",
        "sticky_element",
        "floating_element",
        "parallax_effect",
        "hover_effect",
        "ripple_effect",
        "animation",
        "transition",
        "reveal_animation",
    ],
}

# Font families to use
FONT_FAMILIES = [
    # Sans-serif
    "Arial", "Helvetica", "Verdana", "Tahoma", "Trebuchet MS", "Geneva",
    "Lucida Sans", "Segoe UI", "Open Sans", "Roboto", "Lato", "Montserrat",
    "Source Sans Pro", "Raleway", "Ubuntu", "Nunito", "Poppins", "Inter",
    "Work Sans", "DM Sans", "Plus Jakarta Sans", "Manrope",

    # Serif
    "Times New Roman", "Georgia", "Garamond", "Palatino", "Bookman",
    "Courier New", "Merriweather", "Playfair Display", "Lora", "PT Serif",
    "Crimson Text", "Libre Baskerville", "Spectral", "Source Serif Pro",

    # Monospace
    "Courier", "Consolas", "Monaco", "Lucida Console", "Fira Code",
    "Source Code Pro", "JetBrains Mono", "IBM Plex Mono", "Roboto Mono",

    # Display/Decorative
    "Comic Sans MS", "Impact", "Brush Script MT", "Pacifico", "Lobster",
    "Dancing Script", "Satisfy", "Righteous", "Bebas Neue", "Anton",
]

# Icon libraries to include
ICON_LIBRARIES = [
    "font_awesome",
    "material_icons",
    "bootstrap_icons",
    "feather_icons",
    "heroicons",
    "ionicons",
    "remix_icons",
    "tabler_icons",
    "lucide",
    "phosphor_icons",
]

# Color schemes
COLOR_SCHEMES = [
    "light_mode",
    "dark_mode",
    "high_contrast",
    "blue_theme",
    "green_theme",
    "purple_theme",
    "red_theme",
    "orange_theme",
    "monochrome",
    "pastel",
    "vibrant",
    "muted",
    "corporate",
    "minimalist",
]

def get_all_components():
    """Get flat list of all components"""
    all_components = []
    for category, components in WEB_COMPONENTS.items():
        all_components.extend(components)
    return all_components

def get_component_count():
    """Get total number of unique components"""
    return len(get_all_components())

def get_categories():
    """Get list of all categories"""
    return list(WEB_COMPONENTS.keys())

if __name__ == "__main__":
    print(f"Total component categories: {len(WEB_COMPONENTS)}")
    print(f"Total unique components: {get_component_count()}")
    print(f"\nCategories:")
    for category, components in WEB_COMPONENTS.items():
        print(f"  {category}: {len(components)} components")
