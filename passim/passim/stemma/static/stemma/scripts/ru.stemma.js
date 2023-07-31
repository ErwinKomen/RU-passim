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
      ru.stemma.init_events();

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
        loc_isPointerDown = false,
        loc_pointerOrigin = { x: 0, y: 0 },
        loc_viewBox = { x: 0, y: 0, width: 0, height: 0 },
        loc_newViewBox = {x:0, y:0},
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
        oSyncTimer = null,
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

      getPointFromEvent: function(event) {
        var point = {x:0, y:0};
        // If event is triggered by a touch event, we get the position of the first finger
        if (event.targetTouches) {
          point.x = event.targetTouches[0].clientX;
          point.y = event.targetTouches[0].clientY;
        } else {
          point.x = event.clientX;
          point.y = event.clientY;
        }
  
        return point;
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
      },

      /**
       * init_events
       *    Things that must be done on page-load
       *
       */
      init_events: function () {
        var elAnalyse = "#calc_start_stemma";

        try {
          // Do we have a start stemma button?
          if ($(elAnalyse).length > 0) {
            if ($(elAnalyse).attr("disabled") !== undefined && $(elAnalyse).attr("disabled") === "disabled") {
              // no need to do anything
            } else {
              // Yes, we do, so start the analysis
              $(elAnalyse).click();
              // Now disable the button
              $(elAnalyse).attr("disabled", "disabled");
              $(elAnalyse).removeClass("btn-primary");
              $(elAnalyse).addClass("btn-info");
            }
          }



        } catch (ex) {
          private_methods.errMsg("init_events", ex);
        }
      },

      /**
       *  calc_start
       *      Start calculations
       *
       */
      calc_start: function (sSyncType) {
        var progress_url = "",
            start_url = "",
            target_details = null,
            target_progress = null,
            target_result = null,
            elThis = null,
            oJson = null,
            frm = null,
            data = null;

        try {
          // Get the URL to measure progress and to start
          target_details = "#calc_details_" + sSyncType;
          target_progress = "#calc_progress_" + sSyncType;
          target_result = "#calc_result_" + sSyncType;
          frm = "#calc_form_" + sSyncType;
          elThis = "#calc_start_" + sSyncType;
          start_url = $(elThis).attr("calc-start");
          progress_url = $(elThis).attr("calc-progress");

          // Get the data
          data = $(frm).serializeArray();

          // Set getting status updates in process
          oJson = { 'status': 'started', 'message': '...' };
          ru.stemma.oSyncTimer = window.setTimeout(function () { ru.stemma.calc_progress(sSyncType, oJson); }, 1000);

          // Show that we are going to do something
          $(target_progress).html("Waiting for the first response...");

          // Start up the process
          $.post(start_url, data, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "ok":
                case "finished":
                  // Show we are ready
                  $(target_progress).html("READY!");
                  $(target_details).html($(target_details).html() + "\nFinished!");

                  // If we have results, show them
                  if ($(target_result).length > 0 && response.svg !== undefined) {
                    $(target_result).html(response.svg);
                  }

                  // Make sure we stop nicely
                  ru.stemma.calc_stop(sSyncType, response);
                  break;
                case "error":
                  $(target_progress).html("Stopped by error");
                  $(target_details).html(response.message);
                  break;
                default:
                  // Something went wrong -- show the page or not?
                  private_methods.errMsg("The status returned is unknown: " + response.status);
                  break;
              }

            }
          });

        } catch (ex) {
          private_methods.errMsg("calc_start", ex);
        }
      },

      /**
       *  calc_progress
       *      Return the progress of calculation
       *
       */
      calc_progress: function (sSyncType, options) {
        var oData = {},
            progress_url = "",
            elThis = "",
            target_details = null,
            target_progress = null,
            frm = null,
            data = null;

        try {
          target_details = "#calc_details_" + sSyncType;
          target_progress = "#calc_progress_" + sSyncType;
          frm = "#calc_form_" + sSyncType;
          elThis = "#calc_start_" + sSyncType;
          progress_url = $(elThis).attr("calc-progress");

          // Get the data
          data = $(frm).serializeArray();

          // Ask for progress information
          $.post(progress_url, data, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "error":
                  // Show we are ready
                  $(target_progress).html("Error calculating: " + sSyncType);
                  $(target_details).html(response.message);
                  // Stop the progress calling
                  window.clearInterval(ru.stemma.oSyncTimer);
                  // Leave the routine, and don't return anymore
                case "done":
                case "ready":
                case "finished":
                  // Default action is to show the status
                  $(target_progress).html(response.status);
                  $(target_details).html(response.message);
                  // Finish nicely
                  ru.stemma.calc_stop(sSyncType, response, false);
                  return;
                default:
                  // Default action is to show the status
                  $(target_progress).html(response.status);
                  $(target_details).html(response.message);
                  // Set the timer to make another call
                  oData = response
                  ru.stemma.oSyncTimer = window.setTimeout(function () { ru.stemma.calc_progress(sSyncType, oData); }, 1000);
                  break;
              }
            }
          });
        } catch (ex) {
          private_methods.errMsg("calc_progress", ex);
        }
      },

      /**
       *  calc_stop
       *      Finalize synchronisation
       *
       */
      calc_stop: function (sSyncType, response) {
        var elAnalyse = "#calc_start_stemma",
            ar_param = null,
            svg = $("svg").first()[0];

        // Stop the progress calling
        window.clearInterval(ru.stemma.oSyncTimer);

        // Show we are ready
        $("#calc_progress_" + sSyncType).html("Finished calculation: " + sSyncType + "<br>Last details:");
        $("#calc_details_" + sSyncType).html(response.message);

        // Now enable the button again
        $(elAnalyse).removeAttr("disabled");
        $(elAnalyse).addClass("btn-primary");
        $(elAnalyse).removeClass("btn-info");

        // Install the onwheel event
        $("svg").on("wheel", ru.stemma.zoom_wheel);
        // Panning events
        // If browser supports pointer events
        if (window.PointerEvent) {
          svg.addEventListener('pointerdown', ru.stemma.onPointerDown); // Pointer is pressed
          svg.addEventListener('pointerup', ru.stemma.onPointerUp); // Releasing the pointer
          svg.addEventListener('pointerleave', ru.stemma.onPointerUp); // Pointer gets out of the SVG area
          svg.addEventListener('pointermove', ru.stemma.onPointerMove); // Pointer is moving
        } else {
          // Add all mouse events listeners fallback
          svg.addEventListener('mousedown', ru.stemma.onPointerDown); // Pressing the mouse
          svg.addEventListener('mouseup', ru.stemma.onPointerUp); // Releasing the mouse
          svg.addEventListener('mouseleave', ru.stemma.onPointerUp); // Mouse gets out of the SVG area
          svg.addEventListener('mousemove', ru.stemma.onPointerMove); // Mouse is moving

          // Add all touch events listeners fallback
          svg.addEventListener('touchstart', ru.stemma.onPointerDown); // Finger is touching the screen
          svg.addEventListener('touchend', ru.stemma.onPointerUp); // Finger is no longer touching the screen
          svg.addEventListener('touchmove', ru.stemma.onPointerMove); // Finger is moving
        }

        // Make sure to save the original values from the viewbox
        ar_param = svg.getAttribute('viewBox').split(' ').map(Number);
        loc_viewBox['width'] = ar_param[2];
        loc_viewBox['height'] = ar_param[3];
      },

      /* onPointerDown 
       *
       */
      onPointerDown: function(event) {
        try {
          loc_isPointerDown = true; // We set the pointer as down

          // We get the pointer position on click/touchdown so we can get the value once the user starts to drag
          var pointerPosition = private_methods.getPointFromEvent(event);
          loc_pointerOrigin.x = pointerPosition.x;
          loc_pointerOrigin.y = pointerPosition.y;
        } catch (ex) {
          private_methods.errMsg("onPointerDown", ex);
        }
      },

      /* onPointerUp 
       *
       */
      onPointerUp: function (event) {
        try {
          // The pointer is no longer considered as down
          loc_isPointerDown = false;

          // We save the viewBox coordinates based on the last pointer offsets
          loc_viewBox.x = loc_newViewBox.x;
          loc_viewBox.y = loc_newViewBox.y;
        } catch (ex) {
          private_methods.errMsg("onPointerUp", ex);
        }
      },

      /* onPointerMove
       *
       */
      onPointerMove: function (event) {
        var svg = $("svg").first()[0];

        try {
          // Only run this function if the pointer is down
          if (!loc_isPointerDown) {
            return;
          }
          // This prevent user to do a selection on the page
          event.preventDefault();

          // Get the pointer position
          var pointerPosition = private_methods.getPointFromEvent(event);

          // We calculate the distance between the pointer origin and the current position
          // The viewBox x & y values must be calculated from the original values and the distances
          loc_newViewBox.x = loc_viewBox.x - (pointerPosition.x - loc_pointerOrigin.x);
          loc_newViewBox.y = loc_viewBox.y - (pointerPosition.y - loc_pointerOrigin.y);

          // We create a string with the new viewBox values
          // The X & Y values are equal to the current viewBox minus the calculated distances
          var viewBoxString = `${loc_newViewBox.x} ${loc_newViewBox.y} ${loc_viewBox.width} ${loc_viewBox.height}`;
          // We apply the new viewBox values onto the SVG
          svg.setAttribute('viewBox', viewBoxString);

        } catch (ex) {
          private_methods.errMsg("onPointerMove", ex);
        }
      },

      /* zoom_wheel 
       *
       */
      zoom_wheel: function (event) {
        var ar_point = null,
            ar_wh = null,
            d_point = {},
            d_wh = {},
            xPropW = 0, yPropH = 0,
            width, height,
            width2, height2,
            viewBoxString = "",
            svg = $("svg").first()[0];

        try {

          // Prevent default handling
          event.preventDefault();

          // set the scaling factor (and make sure it's at least 10%)
          let scale = event.originalEvent.deltaY / 1000;
          scale = Math.abs(scale) < .1 ? .1 * event.deltaY / Math.abs(event.deltaY) : scale;

          // get point in SVG space
          let pt = new DOMPoint(event.originalEvent.clientX, event.originalEvent.clientY);
          // pt = pt.matrixTransform(svg.getScreenCTM().inverse());

          // get viewbox transform
          ar_point = svg.getAttribute('viewBox').split(' ').map(Number);
          loc_viewBox.x = ar_point[0];
          loc_viewBox.y = ar_point[1];
          loc_viewBox.width = ar_point[2];
          loc_viewBox.height = ar_point[3];
          //d_point['x'] = ar_point[0];
          //d_point['y'] = ar_point[1];
          //width = ar_point[2];
          //height = ar_point[3];
          // let [x, y, width, height] = svg.getAttribute('viewBox').split(' ').map(Number);

          // get pt.x as a proportion of width and pt.y as proportion of height
          xPropW = (pt.x - loc_viewBox.x) / loc_viewBox.width;
          yPropH = (pt.y - loc_viewBox.y) / loc_viewBox.height;

          // calc new width and height, new x2, y2 (using proportions and new width and height)
          loc_newViewBox.width = loc_viewBox.width + loc_viewBox.width * scale;
          loc_newViewBox.height = loc_viewBox.height + loc_viewBox.height * scale;
          loc_newViewBox.x = pt.x - xPropW * loc_newViewBox.width;
          loc_newViewBox.y = pt.y - yPropH * loc_newViewBox.height;

          viewBoxString = `${loc_newViewBox.x} ${loc_newViewBox.y} ${loc_newViewBox.width} ${loc_newViewBox.height}`;
          // We apply the new viewBox values onto the SVG
          svg.setAttribute('viewBox', viewBoxString);

          // svg.setAttribute('viewBox', `${x2} ${y2} ${width2} ${height2}`);
        } catch (ex) {
          private_methods.errMsg("zoom_wheel", ex);
        }
      },



      // LAST POINT
    }
  }($, ru.config));

  return ru;
}(jQuery, window.ru || {})); // window.ru: see http://stackoverflow.com/questions/21507964/jslint-out-of-scope

