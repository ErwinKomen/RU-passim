var django = {
  "jQuery": jQuery.noConflict(true)
};
var jQuery = django.jQuery;
var $ = jQuery;

var ru = (function ($, ru) {
  "use strict";

  ru.passim.seeker = (function ($, config) {
    // Define variables for ru.passim.seeker here
    var loc_example = "",
        loc_progr = [],       // Progress tracking
        loc_divErr = "passim_err",
        loc_sWaiting = " <span class=\"glyphicon glyphicon-refresh glyphicon-refresh-animate\"></span>",
        lAddTableRow = [
          { "table": "manu_search", "prefix": "manu", "counter": false, "events": ru.passim.init_typeahead }
        ];


    // Private methods specification
    var private_methods = {
      /**
       * fitFeatureBox
       *    Initialize the <svg> in the @sDiv
       * 
       * @param {object} oBound
       * @param {el} elTarget
       * @returns {object}
       */
      fitFeatureBox: function (oBound, elTarget) {
        var rect = null;

        try {
          // Take into account scrolling
          oBound['x'] -= document.documentElement.scrollLeft || document.body.scrollLeft;
          oBound['y'] -= document.documentElement.scrollTop || document.body.scrollTop;
          // Make sure it all fits
          if (oBound['x'] + $(elTarget).width() + oBound['width'] + 10 > $(window).width()) {
            oBound['x'] -= $(elTarget).width() + oBound['width'];
          } else if (oBound['x'] < 0) {
            oBound['x'] = 10;
          }
          if (oBound['y'] + $(elTarget).height() + oBound['height'] + 10 > $(window).height()) {
            oBound['y'] -= $(elTarget).height() + oBound['height'];
          } else if (oBound['y'] < 0) {
            oBound['y'] = 10;
          } else {
            oBound['y'] += oBound['height'] + 10;
          }
          // Take into account scrolling
          oBound['x'] += document.documentElement.scrollLeft || document.body.scrollLeft;
          oBound['y'] += document.documentElement.scrollTop || document.body.scrollTop;
          return oBound;
        } catch (ex) {
          private_methods.showError("fitFeatureBox", ex);
          return oBound;
        }
      },
      /**
       * methodNotVisibleFromOutside - example of a private method
       * @returns {String}
       */
      methodNotVisibleFromOutside: function () {
        return "something";
      },

      /**
       *  is_in_list
       *      whether item called sName is in list lstThis
       *
       * @param {list} lstThis
       * @param {string} sName
       * @returns {boolean}
       */
      is_in_list: function (lstThis, sName) {
        var i = 0;

        try {
          for (i = 0; i < lstThis.length; i++) {
            if (lstThis[i]['name'] === sName) {
              return true;
            }
          }
          // Failure
          return false;
        } catch (ex) {
          private_methods.showError("is_in_list", ex);
          return false;
        }
      },

      /**
       *  get_list_value
       *      get the value of the item called sName is in list lstThis
       *
       * @param {list} lstThis
       * @param {string} sName
       * @returns {string}
       */
      get_list_value: function (lstThis, sName) {
        var i = 0;

        try {
          for (i = 0; i < lstThis.length; i++) {
            if (lstThis[i]['name'] === sName) {
              return lstThis[i]['value'];
            }
          }
          // Failure
          return "";
        } catch (ex) {
          private_methods.showError("get_list_value", ex);
          return "";
        }
      },

      /**
       *  set_list_value
       *      Set the value of the item called sName is in list lstThis
       *
       * @param {list} lstThis
       * @param {string} sName
       * @param {string} sValue
       * @returns {boolean}
       */
      set_list_value: function (lstThis, sName, sValue) {
        var i = 0;

        try {
          for (i = 0; i < lstThis.length; i++) {
            if (lstThis[i]['name'] === sName) {
              lstThis[i]['value'] = sValue;
              return true;
            }
          }
          // Failure
          return false;
        } catch (ex) {
          private_methods.showError("set_list_value", ex);
          return false;
        }
      },

      /**
       * prepend_styles
       *    Get the html in sDiv, but prepend styles that are used in it
       * 
       * @param {el} HTML dom element
       * @returns {string}
       */
      prepend_styles: function (sDiv, sType) {
        var lData = [],
            el = null,
            i, j,
            sheets = document.styleSheets,
            used = "",
            elems = null,
            tData = [],
            rules = null,
            rule = null,
            s = null,
            sSvg = "",
            defs = null;

        try {
          // Get the correct element
          if (sType === "svg") { sSvg = " svg";}
          el = $(sDiv + sSvg).first().get(0);
          // Get all the styles used 
          for (i = 0; i < sheets.length; i++) {
            rules = sheets[i].cssRules;
            for (j = 0; j < rules.length; j++) {
              rule = rules[j];
              if (typeof (rule.style) !== "undefined") {
                elems = el.querySelectorAll(rule.selectorText);
                if (elems.length > 0) {
                  used += rule.selectorText + " { " + rule.style.cssText + " }\n";
                }
              }
            }
          }

          // Get the styles
          s = document.createElement('style');
          s.setAttribute('type', 'text/css');
          switch (sType) {
            case "html":
              s.innerHTML = used;

              // Get the table
              tData.push("<table class=\"func-view\">");
              tData.push($(el).find("thead").first().get(0).outerHTML);
              tData.push("<tbody>");
              $(el).find("tr").each(function (idx) {
                if (idx > 0 && !$(this).hasClass("hidden")) {
                  tData.push(this.outerHTML);
                }
              });
              tData.push("</tbody></table>");

              // Turn into a good HTML
              lData.push("<html><head>");
              lData.push(s.outerHTML);
              lData.push("</head><body>");
              // lData.push(el.outerHTML);
              lData.push(tData.join("\n"));
              
              lData.push("</body></html>");
              break;
            case "svg":
              s.innerHTML = "<![CDATA[\n" + used + "\n]]>";

              defs = document.createElement('defs');
              defs.appendChild(s);
              el.insertBefore(defs, el.firstChild);

              el.setAttribute("version", "1.1");
              el.setAttribute("xmlns", "http://www.w3.org/2000/svg");
              el.setAttribute("xmlns:xlink", "http://www.w3.org/1999/xlink");
              lData.push("<?xml version=\"1.0\" standalone=\"no\"?>");
              lData.push("<!DOCTYPE svg PUBLIC \"-//W3C//DTD SVG 1.1//EN\" \"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd\" >");
              lData.push(el.outerHTML);
              break;
          }

          return lData.join("\n");
        } catch (ex) {
          private_methods.showError("prepend_styles", ex);
          return "";
        }
      },

      /**
       * screenCoordsForRect
       *    Get the correct screen coordinates for the indicated <svg> <rect> element
       * 
       * @param {el} svgRect
       * @returns {object}
       */
      screenCoordsForRect: function (svgRect) {
        var pt = null,
            elSvg = null,
            rect = null,
            oBound = {},
            matrix;

        try {
          // Get the root <svg>
          elSvg = $(svgRect).closest("svg").get(0);

          rect = svgRect.get(0);
          oBound = rect.getBoundingClientRect();

          // Take into account scrolling
          oBound['x'] += document.documentElement.scrollLeft || document.body.scrollLeft;
          oBound['y'] += document.documentElement.scrollTop || document.body.scrollTop;
          return oBound;
        } catch (ex) {
          private_methods.showError("screenCoordsForRect", ex);
          return oBound;
        }

      },
      /**
       *  var_move
       *      Move variable row one step down or up
       *      This means the 'order' attribute changes
       */
      var_move: function (elStart, sDirection, sType) {
        var elRow = null,
            el = null,
            tdCounter = null,
            rowSet = null,
            iLen = 0;

        try {
          // Find out what type we have
          if (sType === undefined) { sType = ""; }
          switch (sType) {
            case "selected":
              // Find the selected row
              elRow = $(elStart).closest("form").find("tr.selected").first();
              // The element is below
              el = $(elRow).find(".var-order input").parent();
              break;
            default:
              // THe [el] is where we start
              el = elStart;
              // The row is above me
              elRow = $(el).closest("tr");
              break;
          }
          // Perform the action immediately
          switch (sDirection) {
            case "down":
              // Put the 'other' (=next) row before me
              $(elRow).next().after($(elRow));
              break;
            case "up":
              // Put the 'other' (=next) row before me
              $(elRow).prev().before($(elRow));
              break;
            default:
              return;
          }
          // Now iterate over all rows in this table
          rowSet = $(elRow).parent().children(".form-row").not(".empty-form");
          iLen = $(rowSet).length;
          $(rowSet).each(function (index, el) {
            var elInput = $(el).find(".var-order input");
            var sOrder = $(elInput).val();
            // Set the order of this element
            if (parseInt(sOrder, 10) !== index + 1) {
              $(elInput).attr("value", index + 1);
              $(elInput).val(index + 1);
              // Look for a <td> element with class "counter"
              tdCounter = $(el).find("td.counter");
              if (tdCounter.length > 0) {
                $(tdCounter).html(index+1);
              }
            }
            if (sType === "") {
              // Check visibility of up and down
              $(el).find(".var-down").removeClass("hidden");
              $(el).find(".var-up").removeClass("hidden");
              if (index === 0) {
                $(el).find(".var-up").addClass("hidden");
              }
              if (index === iLen - 1) {
                $(el).find(".var-down").addClass("hidden");
              }
            }
          });
        } catch (ex) {
          private_methods.errMsg("var_move", ex);
        }
      },
      errMsg: function (sMsg, ex, bNoCode) {
        var sHtml = "",
            bCode = true;

        // Check for nocode
        if (bNoCode !== undefined) {
          bCode = not(bNoCode);
        }
        // Replace newlines by breaks
        sMsg = sMsg.replace(/\n/g, "\n<br>");
        if (ex === undefined) {
          sHtml = "Error: " + sMsg;
        } else {
          sHtml = "Error in [" + sMsg + "]<br>" + ex.message;
        }
        sHtml = "<code>" + sHtml + "</code>";
        console.log(sHtml);
        $("#" + loc_divErr).html(sHtml);
      },
      errClear: function () {
        $("#" + loc_divErr).html("");
        loc_bExeErr = false;
      },
      mainWaitStart : function() {
        var elWait = $(".main-wait").first();
        if (elWait !== undefined && elWait !== null) {
          $(elWait).removeClass("hidden");
        }
      },
      mainWaitStop: function () {
        var elWait = $(".main-wait").first();
        if (elWait !== undefined && elWait !== null) {
          $(elWait).addClass("hidden");
        }
      },
      waitInit: function (el) {
        var elResPart = null,
            elWait = null;

        try {
          // Set waiting div
          elResPart = $(el).closest(".research_part");
          if (elResPart !== null) {
            elWait = $(elResPart).find(".research-fetch").first();
          }
          return elWait;
        } catch (ex) {
          private_methods.errMsg("waitInit", ex);
        }
      },
      waitStart: function(el) {
        if (el !== null) {
          $(el).removeClass("hidden");
        }
      },
      waitStop: function (el) {
        if (el !== null) {
          $(el).addClass("hidden");
        }
      }
    }

    // Public methods
    return {

      /**
       *  init_events
       *      Bind main necessary events
       *
       */
      init_events: function () {
        try {
          // NOTE: only treat the FIRST <a> within a <tr class='add-row'>
          $("tr.add-row").each(function () {
            $(this).find("a").first().click(ru.passim.seeker.tabular_addrow);
          });
          // Bind one 'tabular_deletrow' event handler to clicking that button
          $(".delete-row").unbind("click");
          $('tr td a.delete-row').click(ru.passim.seeker.tabular_deleterow);

          // Bind the click event to all class="ajaxform" elements
          $(".ajaxform").unbind('click').click(ru.passim.seeker.ajaxform_click);
        } catch (ex) {
          private_methods.errMsg("init_events", ex);
        }
      },

      /**
       * search_reset
       *    Clear the information in the form's fields and then do a submit
       *
       */
      search_reset: function (elStart) {
        var frm = null;

        try {
          // Get to the form
          frm = $(elStart).closest('form');
          // Clear the information in the form's INPUT fields
          $(frm).find("input:not([readonly]).searching").val("");
          // Show we are waiting
          $("#waitingsign").removeClass("hidden");
          // Now submit the form
          frm.submit();
        } catch (ex) {
          private_methods.errMsg("search_reset", ex);
        }
      },

      /**
       * search_clear
       *    No real searching, just reset the criteria
       *
       */
      search_clear: function (elStart) {
        var frm = null,
            idx = 0,
            lFormRow = [];

        try {
          // Get to the form
          frm = $(elStart).closest('form');
          // Remove additional rows
          lFormRow = $(frm).find("tr.form-row").not(".empty-form");
          for (idx = lFormRow.length - 1; idx > 0; idx--) {
            // Remove this row
            lFormRow[idx].remove();
          }

          // Clear the fields in the first row
          $(frm).find("input:not([readonly]).searching").val("");

        } catch (ex) {
          private_methods.errMsg("search_clear", ex);
        }
      },

      /**
       * search_start
       *    Clear the information in the form's fields and then do a submit
       *
       */
      search_start: function (elStart) {
        var frm = null;

        try {
          // Get to the form
          frm = $(elStart).closest('form');
          // Show we are waiting
          $("#waitingsign").removeClass("hidden");
          // Now submit the form
          frm.submit();
        } catch (ex) {
          private_methods.errMsg("search_start", ex);
        }
      },

      /**
       * check_progress
       *    Check the progress of reading e.g. codices
       *
       */
      check_progress: function (progrurl, sTargetDiv) {
        var elTarget = "#" + sTargetDiv,
            sMsg = "",
            lHtml = [];

        try {
          $(elTarget).removeClass("hidden");
          // Call the URL
          $.get(progrurl, function (response) {
            // Action depends on the response
            if (response === undefined || response === null || !("status" in response)) {
              private_methods.errMsg("No status returned");
            } else {
              switch (response.status) {
                case "ready":
                case "finished":
                  // NO NEED for further action
                  //// Indicate we are ready
                  //$(elTarget).html("READY");
                  break;
                case "error":
                  // Show the error
                  if ('msg' in response) {
                    $(elTarget).html(response.msg);
                  } else {
                    $(elTarget).html("An error has occurred");
                  }                  
                  break;
                default:
                  if ("msg" in response) { sMsg = response.msg; }
                  // Combine the status
                  sMsg = "<tr><td>" + response.status + "</td><td>" + sMsg + "</td></tr>";
                  // Check if it is on the stack already
                  if ($.inArray(sMsg, loc_progr) < 0) {
                    loc_progr.push(sMsg);
                  }
                  // Combine the status HTML
                  sMsg = "<table>" + loc_progr.join("\n") + "</table>";
                  $(elTarget).html(sMsg);
                  // Make sure we check again
                  window.setTimeout(function () { ru.passim.seeker.check_progress(progrurl, sTargetDiv); }, 200);
                  break;
              }
            }
          });

        } catch (ex) {
          private_methods.errMsg("check_progress", ex);
        }
      },

      /**
       * hide
       *   Hide element [sHide] and 
       *
       */
      hide: function (sHide) {
        try {
          $("#" + sHide).addClass("hidden");
        } catch (ex) {
          private_methods.errMsg("hide", ex);
        }
      },

      /**
       * import_data
       *   Allow user to upload a file
       *
       * Assumptions:
       * - the [el] contains parameter  @targeturl
       * - there is a div 'import_progress'
       * - there is a div 'id_{{ftype}}-{{forloop.counter0}}-file_source'
       *   or one for multiple files: 'id_files_field'
       *
       */
      import_data: function (sKey) {
        var frm = null,
            targeturl = "",
            options = {},
            fdata = null,
            el = null,
            elProg = null,    // Progress div
            elErr = null,     // Error div
            progrurl = null,  // Any progress function to be called
            data = null,
            xhr = null,
            files = null,
            sFtype = "",      // Type of function (cvar, feat, cond)
            elWait = null,
            bDoLoad = false,  // Need to load with a $.get() afterwards
            elInput = null,   // The <input> element with the files
            more = {},        // Additional (json) data to be passed on (from form-data)
            sTargetDiv = "",  // The div where the uploaded reaction comes
            sSaveDiv = "",    // Where to go if saving is needed
            sMsg = "";

        try {
          // The element to use is the key + import_info
          el = $("#" + sKey + "-import_info");
          elProg = $("#" + sKey + "-import_progress");
          elErr = $("#" + sKey + "-import_error");

          // Set the <div> to be used for waiting
          elWait = private_methods.waitInit(el);

          // Get the URL
          targeturl = $(el).attr("targeturl");
          progrurl = $(el).attr("sync-progress");
          sTargetDiv = $(el).attr("targetid");
          sSaveDiv = $(el).attr("saveid");

          if (targeturl === undefined && sSaveDiv !== undefined && sSaveDiv !== "") {
            targeturl = $("#" + sSaveDiv).attr("ajaxurl");
            sTargetDiv = $("#" + sSaveDiv).attr("openid");
            sFtype = $(el).attr("ftype");
            bDoLoad = true;
          }

          if ($(el).is("input")) {
            elInput = el;
          } else {
            elInput = $(el).find("input").first();
          }

          // Show progress
          $(elProg).attr("value", "0");
          $(elProg).removeClass("hidden");
          if (bDoLoad) {
            $(".save-warning").html("loading the definition..." + loc_sWaiting);
            $(".submit-row button").prop("disabled", true);
          }

          // Add data from the <form> nearest to me: 
          frm = $(el).closest("form");
          if (frm !== undefined) { data = $(frm).serializeArray(); }

          for (var i = 0; i < data.length; i++) {
            more[data[i]['name']] = data[i]['value'];
          }
          // Showe the user needs to wait...
          private_methods.waitStart(elWait);

          // Now initiate any possible progress calling
          if (progrurl !== null) {
            loc_progr = [];
            window.setTimeout(function () { ru.passim.seeker.check_progress(progrurl, sTargetDiv); }, 2000);
          }

          // Upload XHR
          $(elInput).upload(targeturl,
            more,
            function (response) {
              // Transactions have been uploaded...
              console.log("done: ", response);

              // Show where we are
              $(el).addClass("hidden");
              $(".save-warning").html("saving..." + loc_sWaiting);

              // First leg has been done
              if (response === undefined || response === null || !("status" in response)) {
                private_methods.errMsg("No status returned");
              } else {
                switch (response.status) {
                  case "ok":
                    // Check how we should react now
                    if (bDoLoad) {
                      // Show where we are
                      $(".save-warning").html("retrieving..." + loc_sWaiting);

                      $.get(targeturl, function (response) {
                        if (response === undefined || response === null || !("status" in response)) {
                          private_methods.errMsg("No status returned");
                        } else {
                          switch (response.status) {
                            case "ok":
                              // Show the response in the appropriate location
                              $("#" + sTargetDiv).html(response.html);
                              $("#" + sTargetDiv).removeClass("hidden");
                              break;
                            default:
                              // Check how/what to show
                              if ("err_view" in response) {
                                private_methods.errMsg(response['err_view']);
                              } else if ("error_list" in response) {
                                private_methods.errMsg(response['error_list']);
                              } else {
                                // Just show the HTML
                                $("#" + sTargetDiv).html(response.html);
                                $("#" + sTargetDiv).removeClass("hidden");
                              }
                              break;
                          }
                          // Make sure events are in place again
                          ru.passim.seeker.init_events();
                          switch (sFtype) {
                            case "cvar":
                              ru.passim.seeker.init_cvar_events();
                              break;
                            case "cond":
                              ru.passim.seeker.init_cond_events();
                              break;
                            case "feat":
                              ru.passim.seeker.init_feat_events();
                              break;
                          }
                          // Indicate we are through with waiting
                          private_methods.waitStop(elWait);
                        }
                      });
                    } else {
                      // Remove all project-part class items
                      $(".project-part").addClass("hidden");
                      // Place the response here
                      $("#" + sTargetDiv).html(response.html);
                      $("#" + sTargetDiv).removeClass("hidden");
                    }
                    break;
                  default:
                    // Check WHAT to show
                    sMsg = "General error (unspecified)";
                    if ("err_view" in response) {
                      sMsg = response['err_view'];
                    } else if ("error_list" in response) {
                      sMsg = response['error_list'];
                    } else {
                      // Indicate that the status is not okay
                      sMsg = "Status is not good. It is: " + response.status;
                    }
                    // Show the message at the appropriate location
                    $(elErr).html("<div class='error'>" + sMsg + "</div>");
                    // Make sure events are in place again
                    ru.passim.seeker.init_events();
                    switch (sFtype) {
                      case "cvar":
                        ru.passim.seeker.init_cvar_events();
                        break;
                      case "cond":
                        ru.passim.seeker.init_cond_events();
                        break;
                      case "feat":
                        ru.passim.seeker.init_feat_events();
                        break;
                    }
                    // Indicate we are through with waiting
                    private_methods.waitStop(elWait);
                    $(".save-warning").html("(not saved)");
                    break;
                }
              }
              private_methods.waitStop(elWait);
            }, function (progress, value) {
              // Show  progress of uploading to the user
              console.log(progress);
              $(elProg).val(value);
            }
          );
          // Hide progress after some time
          setTimeout(function () { $(elProg).addClass("hidden"); }, 1000);

          // Indicate waiting can stop
          private_methods.waitStop(elWait);
        } catch (ex) {
          private_methods.errMsg("import_data", ex);
          private_methods.waitStop(elWait);
        }
      },

      /**
       * tabular_deleterow
       *   Delete one row from a tabular inline
       *
       */
      tabular_deleterow: function () {
        var sId = "",
            elRow = null,
            sPrefix = "",
            elForms = "",
            counter = $(this).attr("counter"),
            bCounter = false,
            iForms = 0,
            prefix = "simplerel",
            bValidated = false;

        try {
          // Get the prefix, if possible
          sPrefix = $(this).attr("extra");
          bCounter = (typeof counter !== typeof undefined && counter !== false && counter !== "");
          elForms = "#id_" + sPrefix + "-TOTAL_FORMS"
          // Find out just where we are
          sId = $(this).closest("div").attr("id");
          // Find out how many forms there are right now
          iForms = $(elForms).val();
          // The validation action depends on this id
          switch (sId) {
            case "manu_search":
              // Indicate that deep evaluation is needed
              bValidated = true;
              break;
          }
          // Continue with deletion only if validated
          if (bValidated) {
            // Get to the row
            elRow = $(this).closest("tr");
            $(elRow).remove();
            // Decrease the amount of forms
            iForms -= 1;
            $(elForms).val(iForms);

            // Re-do the numbering of the forms that are shown
            $(".form-row").not(".empty-form").each(function (idx, elThisRow) {
              var iCounter = 0, sRowId = "", arRowId = [];

              iCounter = idx + 1;
              // Adapt the ID attribute -- if it EXISTS
              sRowId = $(elThisRow).attr("id");
              if (sRowId !== undefined) {
                arRowId = sRowId.split("-");
                arRowId[1] = idx;
                sRowId = arRowId.join("-");
                $(elThisRow).attr("id", sRowId);
              }

              if (bCounter) {
                // Adjust the number in the FIRST <td>
                $(elThisRow).find("td").first().html(iCounter.toString());
              }

              // Adjust the numbering of the INPUT and SELECT in this row
              $(elThisRow).find("input, select").each(function (j, elInput) {
                // Adapt the name of this input
                var sName = $(elInput).attr("name");
                if (sName !== undefined) {
                  var arName = sName.split("-");
                  arName[1] = idx;
                  sName = arName.join("-");
                  $(elInput).attr("name", sName);
                  $(elInput).attr("id", "id_" + sName);
                }
              });
            });

            // The validation action depends on this id (or on the prefix)
            switch (sId) {
              case "search_mode_simple":
                // Update -- NOTE: THIS IS A LEFT-OVER FROM CESAR
                ru.passim.seeker.simple_update();
                break;
            }
          }

        } catch (ex) {
          private_methods.errMsg("tabular_deleterow", ex);
        }
      },

      /**
       * tabular_addrow
       *   Add one row into a tabular inline
       *
       */
      tabular_addrow: function () {
        // NOTE: see the definition of lAddTableRow above
        var arTdef = lAddTableRow,
            oTdef = {},
            rowNew = null,
            elTable = null,
            iNum = 0,     // Number of <tr class=form-row> (excluding the empty form)
            sId = "",
            i;

        try {
          // Find out just where we are
          sId = $(this).closest("div").attr("id");
          // Walk all tables
          for (i = 0; i < arTdef.length; i++) {
            // Get the definition
            oTdef = arTdef[i];
            if (sId === oTdef.table || sId.indexOf(oTdef.table) >= 0) {
              // Go to the <tbody> and find the last form-row
              elTable = $(this).closest("tbody").children("tr.form-row.empty-form")

              // Perform the cloneMore function to this <tr>
              rowNew = ru.passim.seeker.cloneMore(elTable, oTdef.prefix, oTdef.counter);
              // Call the event initialisation again
              if (oTdef.events !== null) {
                oTdef.events();
              }
              // Any follow-up activity
              if ('follow' in oTdef && oTdef['follow'] !== null) {
                oTdef.follow(rowNew);
              }
              // We are done...
              break;
            }
          }
        } catch (ex) {
          private_methods.errMsg("tabular_addrow", ex);
        }
      },

      /**
       *  cloneMore
       *      Add a form to the formset
       *      selector = the element that should be duplicated
       *      type     = the formset type
       *      number   = boolean indicating that re-numbering on the first <td> must be done
       *
       */
      cloneMore: function (selector, type, number) {
        var elTotalForms = null,
            total = 0;

        try {
          // Clone the element in [selector]
          var newElement = $(selector).clone(true);
          // Find the total number of [type] elements
          elTotalForms = $('#id_' + type + '-TOTAL_FORMS').first();
          // Determine the total of already available forms
          if (elTotalForms === null || elTotalForms.length ===0) {
            // There is no TOTAL_FORMS for this type, so calculate myself
          } else {
            // Just copy the TOTAL_FORMS value
            total = $(elTotalForms).val();
          }

          // Find each <input> element
          newElement.find(':input').each(function (idx, el) {
            if ($(el).attr("name") !== undefined) {
              // Get the name of this element, adapting it on the fly
              var name = $(el).attr("name").replace("__prefix__", total.toString());
              // Produce a new id for this element
              var id = $(el).attr("id").replace("__prefix__", total.toString());
              // Adapt this element's name and id, unchecking it
              $(el).attr({ 'name': name, 'id': id }).val('').removeAttr('checked');
            }
          });
          newElement.find('select').each(function (idx, el) {
            if ($(el).attr("name") !== undefined) {
              // Get the name of this element, adapting it on the fly
              var name = $(el).attr("name").replace("__prefix__", total.toString());
              // Produce a new id for this element
              var id = $(el).attr("id").replace("__prefix__", total.toString());
              // Adapt this element's name and id, unchecking it
              $(el).attr({ 'name': name, 'id': id }).val('').removeAttr('checked');
            }
          });

          // Find each <label> under newElement
          newElement.find('label').each(function (idx, el) {
            if ($(el).attr("for") !== undefined) {
              // Adapt the 'for' attribute
              var newFor = $(el).attr("for").replace("__prefix__", total.toString());
              $(el).attr('for', newFor);
            }
          });

          // Look at the inner text of <td>
          newElement.find('td').each(function (idx, el) {
            var elText = $(el).children().first();
            if (elText !== undefined) {
              var sHtml = $(elText).html();
              if (sHtml !== undefined && sHtml !== "") {
                sHtml = sHtml.replace("__counter__", total.toString());
                $(elText).html(sHtml);
              }
              // $(elText).html($(elText).html().replace("__counter__", total.toString()));
            }
          });
          // Look at the attributes of <a>
          newElement.find('a').each(function (idx, el) {
            // Iterate over all attributes
            var elA = el;
            $.each(elA.attributes, function (i, attrib) {
              var attrText = $(elA).attr(attrib.name).replace("__counter__", total.toString());
              // EK (20/feb): $(this).attr(attrib.name, attrText);
              $(elA).attr(attrib.name, attrText);
            });
          });


          // Adapt the total number of forms in this formset
          total++;
          $('#id_' + type + '-TOTAL_FORMS').val(total);

          // Adaptations on the new <tr> itself
          newElement.attr("id", "arguments-" + (total - 1).toString());
          newElement.attr("class", "form-row row" + total.toString());

          // Insert the new element before the selector = empty-form
          $(selector).before(newElement);

          // Should we re-number?
          if (number !== undefined && number) {
            // Walk all <tr> elements of the table
            var iRow = 1;
            $(selector).closest("tbody").children("tr.form-row").not(".empty-form").each(function (idx, el) {
              var elFirstCell = $(el).find("td").not(".hidden").first();
              $(elFirstCell).html(iRow);
              iRow += 1;
            });
          }

          // Return the new <tr> 
          return newElement;

        } catch (ex) {
          private_methods.errMsg("cloneMore", ex);
          return null;
        }
      },

      /**
       * toggle_click
       *   Action when user clicks an element that requires toggling a target
       *
       */
      toggle_click: function (elThis, class_to_close) {
        var elGroup = null,
            elTarget = null,
            sStatus = "";

        try {
          // Get the target to be opened
          elTarget = $(elThis).attr("targetid");
          // Sanity check
          if (elTarget !== null) {
            // Show it if needed
            if ($("#" + elTarget).hasClass("hidden")) {
              $("#" + elTarget).removeClass("hidden");
            } else {
              $("#" + elTarget).addClass("hidden");
              // Check if there is an additional class to close
              if (class_to_close !== undefined && class_to_close !== "") {
                $("." + class_to_close).addClass("hidden");
              }
            }
          }
        } catch (ex) {
          private_methods.errMsg("toggle_click", ex);
        }
      },

    };
  }($, ru.config));

  return ru;
}(jQuery, window.ru || {})); // window.ru: see http://stackoverflow.com/questions/21507964/jslint-out-of-scope

