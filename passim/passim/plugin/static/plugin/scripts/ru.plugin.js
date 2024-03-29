var django = {
  "jQuery": jQuery.noConflict(true)
};
var jQuery = django.jQuery;
var $ = jQuery;

(function ($) {
  $(function () {
    $(document).ready(function () {
      // Initialize event listeners
      ru.plugin.init_events();

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

  ru.plugin = (function ($, config) {
    // Define variables for ru.basic here
    var loc_divErr = "passim_err",
        loc_urlStore = "",      // Keep track of URL to be shown
        loc_progr = [],         // Progress tracking
        loc_columnTh = null,    // TH being dragged
        loc_params = "",        // DCT parameters
        loc_ssglists = null,    // The object with the DCT information
        loc_colwrap = [],       // Column wrapping
        loc_dctdata = [],
        loc_dragDst = null,     // Destination of the dragging
        loc_sWaiting = " <span class=\"glyphicon glyphicon-refresh glyphicon-refresh-animate\"></span>",
        loc_bManuSaved = false,
        loc_keyword = [],           // Keywords that can belong to a sermongold or a sermondescr
        loc_language = [],
        KEYS = {
          BACKSPACE: 8, TAB: 9, ENTER: 13, SHIFT: 16, CTRL: 17, ALT: 18, ESC: 27, SPACE: 32, PAGE_UP: 33, PAGE_DOWN: 34,
          END: 35, HOME: 36, LEFT: 37, UP: 38, RIGHT: 39, DOWN: 40, DELETE: 46
        },
        loc_dctTooltip = [
          { "label": "Gryson/Clavis", "key": "siglist" },
          { "label": "Author", "key": "author" },
          { "label": "PASSIM code", "key": "code" },
          { "label": "Incipit", "key": "incipit" },
          { "label": "Explicit", "key": "explicit" },
          { "label": "Part of HC[s]", "key": "hcs" },
          { "label": "SGs in equality set", "key": "sgcount" },
          { "label": "Links to other SSGs", "key": "ssgcount" },
        ],
        loc_dctTooltipCollection = [
          { "label": "Name",        "key": "name" },
          { "label": "Description", "key": "descr" },
        ],
        loc_dctTooltipAdditional = [
          { "label": "Attributed author", "key": "srm_author" },
          { "label": "Section title",     "key": "srm_sectiontitle" },
          { "label": "Lectio",            "key": "srm_lectio" },
          { "label": "Title",             "key": "srm_title" },
          { "label": "Incipit",           "key": "srm_incipit" },
          { "label": "Explicit",          "key": "srm_explicit" },
          { "label": "Postscriptum",      "key": "srm_postscriptum" },
          { "label": "Feast",             "key": "srm_feast" },
          { "label": "Bible reference",   "key": "srm_bibleref" },
          { "label": "Cod. notes",        "key": "srm_codnotes" },
          { "label": "Notes",             "key": "srm_notes" },
          { "label": "Keywords",          "key": "kws" },
        ],
        dummy = 1;

    // Private methods specification
    var private_methods = {
      /**
       * aaaaaaNotVisibleFromOutside - example of a private method
       * @returns {String}
       */
      aaaaaaNotVisibleFromOutside: function () {
        return "something";
      },
      
      /** 
       *  errClear - clear the error <div>
       */
      errClear: function () {
        $("#" + loc_divErr).html("");
      },

      /** 
       *  errMsg - show error message in <div> loc_divErr
       */
      errMsg: function (sMsg, ex) {
        var sHtml = "Error in [" + sMsg + "]<br>";
        if (ex !== undefined && ex !== null) {
          sHtml = sHtml + ex.message;
        }
        $("#" + loc_divErr).html(sHtml);
      },

      /** 
       *  waitInit - initialize waiting
       */
      waitInit: function (el) {
        var elWaith = null;

        try {
          // Right now no initialization is defined
          return elWait;
        } catch (ex) {
          private_methods.errMsg("waitInit", ex);
        }
      },

      /** 
       *  waitStart - Start waiting by removing 'hidden' from the DOM point
       */
      waitStart: function (el) {
        if (el !== null) {
          $(el).removeClass("hidden");
        }
      },

      /** 
       *  waitStop - Stop waiting by adding 'hidden' to the DOM point
       */
      waitStop: function (el) {
        if (el !== null) {
          $(el).addClass("hidden");
        }
      }
    }
    // Public methods
    return {

      init_events: function () {
        var i;

        try {
          // Make sure slider values get updated
          $(".slider").change(function () {
            var el = $(this),
                elvalue = null,
                value = 0 ;

            value = $(el).val();
            elvalue = "#" + $(el).attr("valueid");
            $(elvalue).html(value);
          });

          // When a .nav-item is pressed, we need to respond
          $(".nav-item a").on("click", function () {
            var el = $(this),
                backupid = "",
                targetid = "",
                name = "";
            // Determine what the name is
            name = $(el).attr("id").replace("nav-", "");
            targetid = "#tab-" + name;
            backupid = targetid + "-backup";
            switch (name) {
              case "clustering":
                $("#clustering_params").removeClass("hidden");
                $("#umap_params").addClass("hidden");
                break;
              case "umap":
                $("#umap_params").removeClass("hidden");
                $("#clustering_params").addClass("hidden");
                break;
              case "ser_hm":  // series heatmap
                $("#umap_params").addClass("hidden");
                $("#clustering_params").addClass("hidden");
                break;
              case "serm_hm": // sermons heatmap
                $("#umap_params").addClass("hidden");
                $("#clustering_params").addClass("hidden");
                break;
            }
            // Show the backup stuff
            $("#tab-content").html($(backupid).html());
          });
        } catch (ex) {
          private_methods.errMsg("init_events", ex);
        }
      },

      /**
       * do_board
       *    Perform apply or reset in the sermonboard
       *
       */
      do_board: function (el, brd_action) {
        var frm = null,
            data = null,
            afterurl = "",
            elActiveTab = "#brd-id_active_tab",
            sActive = "",
            lHtml = [],
            elAct = null,
            sHtml = "",
            targeturl = null,
            err = "",
            targetid = "#tab-content",
            backupid = "",
            elWait = "#loading";

        try {
          // Get the form
          frm = $(el).attr("formid");
          if ($(frm).length === 0) { return; }

          // get the targeturl
          targeturl = $(el).attr("targeturl");
          if (targeturl === undefined || targeturl === "") { return; }

          // Find out what the active tab is
          elAct = $("#tabs").parent().find(".tab-pane.active").first();
          sActive = $(elAct).attr("id");
          $(elActiveTab).val(sActive);
          // targetid = "#"+ sActive;
          err = targetid;
          backupid = "#" + sActive + "-backup";
          // Clear the current target
          $(targetid).html("calculating...")

          // Actually prepare the data
          data = $(frm).serializeArray();

          // Show the waiting symbol in 'loading'
          $(elWait).removeClass("hidden");
          // We have a form, submit it and get the results back
          $.post(targeturl, data, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "ok":
                  // Everything is okay, try to show the HTML
                  sHtml = response.html;
                  if (sHtml === undefined || sHtml === "") {
                    sHtml = "The response is empty";
                  }
                  // Show it
                  $(targetid).html(sHtml);

                  // Copy to the correct backup id
                  $(backupid).html(sHtml);
                  break;
                case "error":
                  if ("html" in response) {
                    // Show the HTML in the targetid
                    $(err).html(response['html']);
                    // If there is an error, indicate this
                    if (response.status === "error") {
                      if ("msg" in response) {
                        if (typeof response['msg'] === "object") {
                          lHtml = []
                          lHtml.push("Errors:");
                          $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                          $(err).html(lHtml.join("<br />"));
                        } else {
                          $(err).html("Error: " + response['msg']);
                        }
                      } else {
                        $(err).html("<code>There is an error</code>");
                      }
                    }
                  } else {
                    // Send a message
                    $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                  }
                  break;
                default:
                  // Something went wrong -- show the page or not?
                  $(err).html("The status returned is unknown: " + response.status);
                  break;
              }
            }
            // Return to view mode
            $(".view-mode").removeClass("hidden");
            $(".edit-mode").addClass("hidden");
            // Hide waiting symbol
            $(".waiting").addClass("hidden");
            // Perform init again
            ru.plugin.init_events();
          });

        } catch (ex) {
          private_methods.errMsg("do_board", ex);
        }
      },


      /**
       * postsubmit
       *    Submit nearest form as POST
       *
       */
      postsubmit: function (el) {
        var frm = null;

        try {
          frm = $(el).closest("form");
          // Make sure we do a POST
          frm.attr("method", "POST");
          // Submit
          $(frm).submit();
        } catch (ex) {
          private_methods.errMsg("postsubmit", ex);
        }
      }



      // LAST POINT
    }
  }($, ru.config));

  return ru;
}(jQuery, window.ru || {})); // window.ru: see http://stackoverflow.com/questions/21507964/jslint-out-of-scope

