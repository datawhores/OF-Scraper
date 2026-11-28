def get_ad_key_words():
    # "#ad" and "#ads" count only as whole tags, so "#adult" and "#adorable"
    # get through; the longer words still match as prefixes, as before
    # ("#advert", "#advertisement", "#sponsoredpost", "#promotions").
    # "user promo" counts after a mention ("@name promo") or at the start of
    # a line, not inside ordinary sentences ("every user promo code...").
    # "trial" was dropped as "discount" and "limited time" were:
    # creators end ordinary posts with "free trial" links to their own page.
    # Keep the pattern all lower-case: post_neg_text_filter matches a
    # lower-case pattern in any case, and any capital (as "AD" or "\B" were)
    # makes it case-sensitive, letting "#Ad" or "Giveaway" through.
    return r"(#(?:ads?\b|advert|sponsored|promotion)|giveaway|@[\w.]+\s+promo|(?:^|\n)[ \t]*user\s+promo|shoutout|endorsement)"
