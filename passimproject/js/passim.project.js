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

        /*
        // Make sure #footinfo stays on bottom if it gets too high
        $("a[data-toggle=tab]").on("click", function (ev) {
          var elLi = null,
              elUl = null;

          elLi = $(this).closest("li");
          elUl = $(elLi).closest("ul");
          $(elUl).children("li").removeClass("active");
          $(elLi).addClass("active");

          // ev.preventDefault();
          // ev.stopPropagation();
          // return true;
        });
        */
        /*
        // Make sure #footinfo stays on bottom if it gets too high
        $("a[data-toggle=tab]").on("mouseup", function (e) {
          var elLi = null,
              elUl = null;

          e.preventDefault();
          $(this).tab('show');
          elLi = $(this).closest("li");
          elUl = $(elLi).closest("ul");
          $(elUl).children("li").removeClass("active");
          $(elLi).addClass("active");
        });

        /*
        $('li a').unbind("click").on("click", function (e) {
          $('a').removeClass('active');
          $(this).parent().addClass('active');

          e.preventDefault();
          e.stopPropagation();
          $(this).tab('show');
          // return true;
        });
        /**/
      },


    };
  }($, ru.config));

  return ru;
}(jQuery, window.ru || {})); // window.ru: see http://stackoverflow.com/questions/21507964/jslint-out-of-scope

