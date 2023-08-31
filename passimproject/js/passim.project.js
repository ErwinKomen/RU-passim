var django = {
  "jQuery": jQuery.noConflict(true)
};
var jQuery = django.jQuery;
var $ = jQuery;

(function ($) {
  $(function () {
    $(document).ready(function () {
      // Initialize event listeners
      ru.passimproject.init_event_listeners();
      // Initialize Bootstrap popover
      // Note: this is used when hovering over the question mark button
      $('[data-toggle="popover"]').popover();
    });
  });
})(django.jQuery);


// based on the type, action will be loaded

// var $ = django.jQuery.noConflict();

var ru = (function ($, ru) {
  "use strict";

  ru.passimproject = (function ($, config) {
    // Define variables for ru.collbank here
    var loc_divErr = "passim_err",
        lst_seconds = ["one", "two", "three", "four", "five", "six", "seven"],
        loc_newUrl = "https://www.ru.nl/en/research/research-projects/passim-project",
        loc_interval = null,
        loc_seconds = 3,
        loc_take_new_url = true,
        base_url = "",
        oSyncTimer = null;

    // Private methods specification
    var private_methods = {
      /**
       * methodNotVisibleFromOutside - example of a private method
       * @returns {String}
       */
      methodNotVisibleFromOutside: function () {
        return "something";
      },
      updateSecs: function() {
        var sText = "";

        try {
          // Calculate the new seconds
          loc_seconds--;
          if (loc_seconds < 0) {
            clearInterval(loc_interval);
            // Do the redirect
            document.location.href = loc_newUrl;
          } else {
            // Show where we are
            sText = 'in <b id="seconds" style="color: red;">' + lst_seconds[loc_seconds] + '</b> seconds...';
            document.getElementById("seconds").innerHTML = sText;

            //// More showing...
            //sText = 'within ' + lst_seconds[loc_seconds + 1] + ' seconds';
            //document.getElementById("plain").innerHTML = sText;
          }

        } catch (ex) {
          private_methods.errMsg("updateSecs", ex);
        }
      },
      errClear: function() {
        $("#" + loc_divErr).html("");
      },
      errMsg: function (sMsg, ex) {
        var sHtml = "Error in [" + sMsg + "]<br>" + ex.message;
        $("#" + loc_divErr).html(sHtml);
      }
    }

    // Public methods
    return {

      init_event_listeners: function () {
        var moveid = "#page_moved",
            msg = "The Passim project page has moved. You will be redirected in <span id=\"seconds\">...</span>";

        // Call the countdown-timer
        if (loc_take_new_url) {
          // Add the has moved message
          $(moveid).html(msg);
          // Start counting down
          ru.passimproject.countdownTimer();
        }
      },

      countdownTimer: function () {
        var one_second = 1000;
        try {
          loc_interval = setInterval(function () { private_methods.updateSecs(); }, one_second);
        } catch (ex) {
          private_methods.errMsg("countdownTimer", ex);
        }
      }

    };
  }($, ru.config));

  return ru;
}(jQuery, window.ru || {})); // window.ru: see http://stackoverflow.com/questions/21507964/jslint-out-of-scope

