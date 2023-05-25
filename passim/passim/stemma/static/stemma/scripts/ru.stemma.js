var django = {
  "jQuery": jQuery.noConflict(true)
};
var jQuery = django.jQuery;
var $ = jQuery;

(function ($) {
  $(function () {
    $(document).ready(function () {
      // Initialize event listeners
      // ru.dct.load_dct();
      // ru.dct.init_selection();

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

  ru.stemma = (function ($, config) {
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
      
      copyToClipboard: function(elem) {
        // create hidden text element, if it doesn't already exist
        var targetId = "_hiddenCopyText_";
        var elConfirm = "";
        var isInput = "";
        var origSelectionStart, origSelectionEnd;

        try {
          // Get to the right element
          if (elem.tagName === "A") {
            elem = $(elem).closest("div").find("textarea").first().get(0);
          }
          isInput = elem.tagName === "INPUT" || elem.tagName === "TEXTAREA";
          if (isInput) {
            // can just use the original source element for the selection and copy
            target = elem;
            origSelectionStart = elem.selectionStart;
            origSelectionEnd = elem.selectionEnd;
          } else {
            // must use a temporary form element for the selection and copy
            target = document.getElementById(targetId);
            if (!target) {
              var target = document.createElement("textarea");
              target.style.position = "absolute";
              target.style.left = "-9999px";
              target.style.top = "0";
              target.id = targetId;
              document.body.appendChild(target);
            }
            target.textContent = elem.textContent;
          }
          // select the content
          var currentFocus = document.activeElement;
          target.focus();
          target.setSelectionRange(0, target.value.length);

          // copy the selection
          var succeed;
          try {
            succeed = document.execCommand("copy");
            console.log("Copied: " + target.value);
            elConfirm = $(elem).closest("div").find(".clipboard-confirm").first();
            $(elConfirm).html("Copied!");
            setTimeout(function () {
              $(elConfirm).fadeOut().empty();
            }, 4000);
          } catch (e) {
            succeed = false;
            console.log("Could not copy");
          }
          // restore original focus
          if (currentFocus && typeof currentFocus.focus === "function") {
            currentFocus.focus();
          }

          if (isInput) {
            // restore prior selection
            elem.setSelectionRange(origSelectionStart, origSelectionEnd);
          } else {
            // clear temporary content
            target.textContent = "";
          }
          
          return succeed;
        } catch (ex) {
          private_methods.errMsg("copyToClipboard", ex);
          return "";
        }

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
      /**
       * do_stemitem
       *    Check or uncheck items for selection
       *
       */
      do_stemitem: function (elStart, sAction) {
        var frm = null,
            targeturl = "",
            action = "",
            elTd = null,
            i = 0,
            elSelItemOne = "#stemitem-one",
            elSelItemRset = "#stemitem-rset",
            err = "#little_err_msg",
            stemitemcount = "",
            data = null;

        try {
          // Figure out what we are doing
          if ($(elSelItemOne).length === 0) {
            // Need to change this stuff
          }
          // In general: hide the -rset
          $(elSelItemRset).addClass("hidden");

          // Is this just canceling?
          switch (sAction) {
            case "cancel_item":
              // This is just canceling the current idea of selecting a Research Set
              $(elSelItemOne).addClass("hidden");
              return;
            case "show_item":
              // Make sure the researcher can select a Research Set
              $(elSelItemOne).removeClass("hidden");
              $(elSelItemRset).addClass("hidden");
              return;
          }

          // Get to the form
          if ($(elStart)[0].localName.toLowerCase() === "form") {
            frm = $(elStart);
          } else {
            frm = $(elStart).closest(".stemitem").attr("targetid");
          }
          // Get the data
          data = $(frm).serializeArray();
          // Append the action to it
          data.push({name: "mode", value: sAction});

          // Find nearest <td>
          elTd = $(elStart).closest("td");

          // Get the URL
          targeturl = $(frm).attr("targeturl");

          // Double check
          $.post(targeturl, data, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "ok":
                  // Should have a new target URL
                  targeturl = response['targeturl'];
                  action = response['action'];
                  // Get stemitemcount
                  stemitemcount = response['stemitemcount'];
                  if (targeturl !== undefined && targeturl !== "") {
                    // Go open that targeturl
                    window.location = targeturl;
                  } else if (action !== undefined && action !== "") {
                    switch (action) {
                      case "update_sav":
                        // Adapt all relevant material
                        $(".stemitem-button-selected").each(function (idx, el) {
                          var elTd = $(el).closest("td"),
                              elTr = $(el).closest("tr");

                          // Change the class
                          $(el).removeClass("stemitem-button-selected");
                          $(el).addClass("stemitem-button");
                          $(el).html('<span class="glyphicon glyphicon-unchecked"></span>');
                          $(el).attr("title", "Select this item");
                          // Change the sitem action to be taken
                          $(elTd).find("#id_stemitemaction").val("add");

                          // Make sure the SavedItem is showing
                          el = $(elTr).find(".sitem-button").first();
                          if (el.length > 0) {
                            $(el).find("span").removeClass("glyphicon-star-empty");
                            $(el).find("span").addClass("glyphicon-star");
                            $(el).removeClass("sitem-button");
                            $(el).addClass("sitem-button-selected");
                            // $(el).attr("onclick", 'ru.dct.do_saveditem(this, "add");');
                            $(el).attr("title", "Remove from your saved items");

                            $(el).unbind("click").on("click", function (evt) {
                              ru.stem.do_saveditem(elStart, "remove");
                            });
                            $(el).closest("td").find("#id_sitemaction").val("remove");
                          }
                        });

                        // Adapt stemitemcount
                        stemitemcount = 0;
                        break;
                      case "update_basket":
                        // Check if this is a new basket
                        if (response['newbasket'] !== undefined) {
                          frm = response['newbasket'];
                          $(frm).submit();
                        }
                        // Adapt all relevant material
                        $(".stemitem-button-selected").each(function (idx, el) {
                          var elTd = $(el).closest("td"),
                              elTr = $(el).closest("tr");

                          // Change the class
                          $(el).removeClass("stemitem-button-selected");
                          $(el).addClass("stemitem-button");
                          $(el).html('<span class="glyphicon glyphicon-unchecked"></span>');
                          $(el).attr("title", "Select this item");
                          // Change the sitem action to be taken
                          $(elTd).find("#id_stemitemaction").val("add");

                        });

                        // Make sure the Basket number is showing correctly
                        $("#basketsize").html("(" + response.basketsize + ")");

                        // Adapt stemitemcount
                        stemitemcount = 0;
                        break;
                      case "update_stem":
                        // Adapt all relevant material
                        $(".stemitem-button-selected").each(function (idx, el) {
                          var elTd = $(el).closest("td"),
                              elTr = $(el).closest("tr");

                          // Change the class
                          $(el).removeClass("stemitem-button-selected");
                          $(el).addClass("stemitem-button");
                          $(el).html('<span class="glyphicon glyphicon-unchecked"></span>');
                          $(el).attr("title", "Select this item");
                          // Change the sitem action to be taken
                          $(elTd).find("#id_stemitemaction").val("add");

                        });
                        // Adapt stemitemcount
                        stemitemcount = 0;
                        // Also make sure to close the stemitem-item
                        $(elSelItemOne).addClass("hidden");
                        $(elSelItemRset).find("a").first().attr("href", response.researchset);
                        $(elSelItemRset).removeClass("hidden");
                        break;
                      case "clear_sel":
                        // Adapt all relevant material
                        $(".stemitem-button-selected").each(function (idx, el) {
                          var elTd = $(el).closest("td");

                          // Change the class
                          $(el).removeClass("stemitem-button-selected");
                          $(el).addClass("stemitem-button");
                          $(el).html('<span class="glyphicon glyphicon-unchecked"></span>');
                          $(el).attr("title", "Select this item");
                          // Change the sitem action to be taken
                          $(elTd).find("#id_stemitemaction").val("add");
                        });
                        break;
                      case "deleted":
                      case "removed":
                        $(elStart).removeClass("stemitem-button-selected");
                        $(elStart).addClass("stemitem-button");
                        $(elStart).html('<span class="glyphicon glyphicon-unchecked"></span>');
                        $(elStart).attr("title", "Select this item");
                        // Change the sitem action to be taken
                        $(elTd).find("#id_stemitemaction").val("add");
                        break;
                      case "added":
                        // $(elStart).css("color", "red");
                        $(elStart).removeClass("stemitem-button");
                        $(elStart).addClass("stemitem-button-selected");
                        $(elStart).html('<span class="glyphicon glyphicon-check"></span>');
                        $(elStart).attr("title", "Uncheck this item");
                        // Change the sitem action to be taken
                        $(elTd).find("#id_stemitemaction").val("remove");
                        break;
                    }
                    // Adapt the amount of selected items
                    if (stemitemcount !== undefined) {
                      if (stemitemcount <= 0) {
                        $(".selcount").html("");
                        $(".select-execute button").attr("disabled", true);
                      } else {
                        $(".selcount").html(stemitemcount);
                        $(".select-execute button").attr("disabled", false);
                      }
                    }
                  }
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
          });


        } catch (ex) {
          private_methods.errMsg("do_stemitem", ex);
        }
      }

      // LAST POINT
    }
  }($, ru.config));

  return ru;
}(jQuery, window.ru || {})); // window.ru: see http://stackoverflow.com/questions/21507964/jslint-out-of-scope

