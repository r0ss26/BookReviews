// make search results table clickable
$(document).ready(function($) {
    $(".search-result").click(function() {
        window.location = $(this).data("href");
    })
})