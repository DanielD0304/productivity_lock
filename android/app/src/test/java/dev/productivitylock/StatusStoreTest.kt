package dev.productivitylock

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.LocalDateTime

class StatusStoreTest {
    private val sites = StatusStore.DEFAULT_SITES

    @Test
    fun matchesTheSiteWithOrWithoutSchemeAndSubdomain() {
        assertEquals("instagram.com", StatusStore.blockedSite("instagram.com", sites))
        assertEquals("instagram.com", StatusStore.blockedSite("https://www.instagram.com/p/abc?x=1", sites))
        assertEquals("instagram.com", StatusStore.blockedSite("m.Instagram.com/reels", sites))
        assertEquals("reddit.com", StatusStore.blockedSite("old.reddit.com", sites))
        assertEquals("linkedin.com", StatusStore.blockedSite("de.linkedin.com/in/someone", sites))
        assertEquals("youtube.com", StatusStore.blockedSite("youtube.com:443/watch", sites))
    }

    @Test
    fun leavesOtherSitesAndSearchesAlone() {
        assertNull(StatusStore.blockedSite("leetcode.com/problems", sites))
        assertNull(StatusStore.blockedSite("notinstagram.com", sites))
        assertNull(StatusStore.blockedSite("instagram.com.evil.example", sites))
        assertNull(StatusStore.blockedSite("instagram login hilfe", sites))
        assertNull(StatusStore.blockedSite("google.com/search?q=reddit.com", sites))
        assertNull(StatusStore.blockedSite("", sites))
        assertNull(StatusStore.blockedSite(null, sites))
    }

    @Test
    fun theLearningDayStartsAtTheRolloverHour() {
        assertEquals("2026-11-19", StatusStore.logicalDay(4, LocalDateTime.of(2026, 11, 20, 3, 59)))
        assertEquals("2026-11-20", StatusStore.logicalDay(4, LocalDateTime.of(2026, 11, 20, 4, 0)))
    }
}
